import os
import sys
from flask import Flask, jsonify, request, Response, stream_with_context
from datetime import datetime
from functools import wraps
from psycopg_pool import ConnectionPool
import json
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.supa_db import SupabaseDB
from utils.elo import Elo
from config.config import (DB_DSN, BASE_ETA_SECONDS, MATCHMAKING_TIMEOUT, MATCHMAKING_POLL_INTERVAL,
                           INITIAL_COMPAT_THRESHOLD, MINIMUM_COMPAT_THRESHOLD, DECAY_RATE_PER_SECOND)
from utils.mm_logic import compat_score, eta_seconds

app = Flask(__name__)

# Configuration
app.config['DEBUG'] = True
app.config['JSON_SORT_KEYS'] = False

# Initialize PostgreSQL connection pool (for matchmaking only - needs row locking)
try:
    if DB_DSN:
        pool = ConnectionPool(
            conninfo=DB_DSN,
            min_size=1,
            max_size=8,
            kwargs={"prepare_threshold": None}  # Disable prepared statements
        )
        print("✓ PostgreSQL connection pool initialized")
    else:
        pool = None
        print("⚠ DATABASE_URL not set, matchmaking disabled")
except Exception as e:
    print(f"✗ PostgreSQL connection pool failed: {e}")
    pool = None

# Initialize Supabase database client (for standard CRUD operations)
try:
    db = SupabaseDB()
    print("✓ Supabase connected successfully")
except Exception as e:
    print(f"✗ Supabase connection failed: {e}")
    db = None


# Decorator to prevent operations on completed matches
def prevent_if_complete(func):
    """
    Decorator that checks if a match is already complete.
    Prevents the endpoint from running if is_complete is True.
    
    Works with match_id from either:
    - URL parameter: /match/cancel/<match_id>
    - JSON body: {"match_id": 123}
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Try to get match_id from URL parameters first
        match_id = kwargs.get('match_id')
        
        # If not in URL, try to get from JSON body
        if match_id is None:
            data = request.get_json()
            if data:
                match_id = data.get('match_id')
        
        # If we still don't have match_id, proceed (might be a start endpoint)
        if match_id is None:
            return func(*args, **kwargs)
        
        # Query the match
        game_search = db.query_table("match_tx", id=match_id)
        
        if not game_search:
            return jsonify({
                'success': False,
                'message': 'Match not found',
                'match_id': match_id
            }), 404
        
        game_data = game_search[0]
        
        # Check if match is already complete
        if game_data.get('is_complete'):
            return jsonify({
                'success': False,
                'message': 'Match already completed',
                'match_id': match_id
            }), 400
        
        # Match is not complete, proceed with endpoint
        return func(*args, **kwargs)
    
    return wrapper

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'flask-server'
    })


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        'error': 'Not found',
        'status': 404
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    return jsonify({
        'error': 'Internal server error',
        'status': 500
    }), 500






@app.route("/match/start", methods=["POST"])
def start_match():
    """Start a match"""
    data = request.get_json()
    user_one_id = data["user_one_id"]
    user_two_id = data["user_two_id"]
    match_score = {user_one_id: 0, user_two_id: 0}

    user_one_elo = db.query_table("users", user_uid=user_one_id)[0]['elo']
    user_two_elo = db.query_table("users", user_uid=user_two_id)[0]['elo']

    tx = db.insert_record("match_tx", {
        "user_one_id": user_one_id,
        "user_two_id": user_two_id,
        "score": match_score,
        'elo_diff': user_one_elo - user_two_elo,
        "is_complete": False
    })

    return jsonify({
        "message": "Match started",
        "match_id": tx[0]['id']
    }), 201
    
@app.route("/match/cancel/<match_id>", methods=["GET"])
@prevent_if_complete
def cancel_match(match_id):
    """Cancel a match"""
    game_search = db.query_table("match_tx", id=match_id)
    game_data = game_search[0]

    user_one_id = game_data['user_one_id']
    user_two_id = game_data['user_two_id']
    db.update_record("match_tx", match_id, {
        "is_complete": True,
        "score": {user_one_id: 0, user_two_id: 0},
        "match_winner": None,
        'settled_at': datetime.now().isoformat()
    })

    return jsonify({
        "message": "Match cancelled",
        "match_id": match_id
    }), 201


@app.route("/match/finish", methods=["POST"])
@prevent_if_complete
def finish_match():
    """Finish a match"""
    data = request.get_json()
    match_id = data['match_id']
    match_score = data['score']

    game_search = db.query_table("match_tx", id=match_id)
    game_data = game_search[0]

    user_one_id = game_data['user_one_id']
    user_two_id = game_data['user_two_id']

    user_one_elo = db.query_table("users", user_uid=user_one_id)[0]['elo']
    user_two_elo = db.query_table("users", user_uid=user_two_id)[0]['elo']

    if match_score[0] > match_score[1]:
        winner_id = user_one_id
    else:
        winner_id = user_two_id

    def S_determine(user_id, winner_id):
        return 1 if user_id == winner_id else 0

    print(game_data)
    print(match_score)
    final_score = {game_data['user_one_id']: match_score[0], game_data['user_two_id']: match_score[1]}

    # Use transaction to ensure all-or-nothing updates
    try:
        with db.transaction() as tx:
            tx.update_record("match_tx", match_id, {
                "is_complete": True,
                "score": final_score,
                "match_winner": winner_id,
                'settled_at': datetime.now().isoformat()
            })
            
            tx.update_by("users", "user_uid", user_one_id, {
                'elo': round(Elo.get_new_elo(user_one_elo, S_determine(user_one_id, winner_id), Elo.get_expected_score(user_one_elo, user_two_elo)))
            })
            
            tx.update_by("users", "user_uid", user_two_id, {
                'elo': round(Elo.get_new_elo(user_two_elo, S_determine(user_two_id, winner_id), Elo.get_expected_score(user_two_elo, user_one_elo)))
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Transaction failed: {str(e)}',
            'match_id': match_id
        }), 500

    return jsonify({
        'message': 'Match finished',
        'received': data,
        'match_id': match_id
    }), 201


# ============================================================================
# MATCHMAKING ENDPOINT - Uses Connection Pool (requires row locking)
# ============================================================================

@app.post("/match")
def match_or_queue():
    """
    Blocking matchmaking endpoint - keeps searching until match found or timeout.
    Uses direct PostgreSQL connection pool (not SupabaseDB) because it requires:
    - FOR UPDATE SKIP LOCKED (pessimistic locking)
    - Atomic transactions with COMMIT/ROLLBACK
    - High performance for continuous searching
    """
    if not pool:
        return jsonify(error="Matchmaking unavailable (no database pool)"), 503
    
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    if not user_id:
        return jsonify(error="Missing user_id"), 400

    start_time = time.time()
    
    # Get user profile and check for existing active matches
    with pool.connection() as conn:
        with conn.cursor() as cur:
            # 1) Check if user already has an active match
            cur.execute("""
                select id from match_tx
                where (user_one_id = %s or user_two_id = %s)
                  and is_complete = false
                limit 1
                """, (user_id, user_id))
            active_match = cur.fetchone()
            
            if active_match:
                return jsonify(
                    error="Already in active match",
                    message="You must finish your current match before queueing again",
                    active_match_id=str(active_match[0])
                ), 400
            
            # 2) Get user profile
            cur.execute("""
                select u.user_uid as user_id, u.area, u.elo,
                       coalesce(u.preferences, '{}'::jsonb) as prefs
                from users u
                where u.user_uid = %s
                """, (user_id,))
            row = cur.fetchone()
            if not row:
                return jsonify(error="User not found"), 404
            
            me_user, me_area, me_elo, me_prefs = row[0], row[1], row[2], row[3]

    # Queue user immediately with timestamp
    queue_time = time.time()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into mm_ticket (user_id, area, elo, prefs, status, created_at)
                values (%s, %s, %s, %s, 'queued', NOW())
                on conflict (user_id) where mm_ticket.status='queued'
                do update set area=excluded.area, elo=excluded.elo, prefs=excluded.prefs, created_at=NOW()
                """, (me_user, me_area, me_elo, json.dumps(me_prefs)))

    # Keep searching until match found or timeout
    attempt = 0
    while time.time() - start_time < MATCHMAKING_TIMEOUT:
        attempt += 1
        wait_time = time.time() - queue_time
        
        # Calculate adjusted threshold based on time waiting
        # Starts at 8.0, decays by 0.05 per second, minimum 3.0
        adjusted_threshold = max(
            MINIMUM_COMPAT_THRESHOLD,
            INITIAL_COMPAT_THRESHOLD - (wait_time * DECAY_RATE_PER_SECOND)
        )
        
        try:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # FIRST: Check if someone else already matched with us
                    cur.execute("""
                        select m.id, m.user_one_id, m.user_two_id, m.compat_score
                        from match_tx m
                        where (m.user_one_id = %s or m.user_two_id = %s)
                          and m.is_complete = false
                        limit 1
                        """, (me_user, me_user))
                    existing_match = cur.fetchone()
                    
                    if existing_match:
                        # We've been matched by another user!
                        match_id, user_one, user_two, compat = existing_match
                        # Clean up our own ticket
                        cur.execute("delete from mm_ticket where user_id=%s and status='queued'", (me_user,))
                        
                        elapsed = time.time() - start_time
                        return jsonify(
                            matched=True,
                            match_id=str(match_id),
                            compat_score=compat,
                            wait_time=round(elapsed, 1),
                            attempts=attempt,
                            matched_by="opponent"
                        ), 200
                    
                    # Lock and scan candidates
                    cur.execute("""
                        with c as (
                          select t.id, t.user_id, t.elo, t.prefs, t.created_at
                          from mm_ticket t
                          where t.status = 'queued'
                            and t.area   = %s
                            and t.user_id <> %s
                          order by t.created_at asc
                          limit 50
                          for update skip locked
                        )
                        select id, user_id, elo, prefs from c
                        """, (me_area, me_user))
                    candidates = cur.fetchall()

                    # Find best match
                    best = None
                    best_score = -1
                    for (tid, uid, elo, prefs) in candidates:
                        s = compat_score(me_elo, me_prefs, elo, prefs)
                        if s > best_score:
                            best = {"ticket_id": tid, "user_id": uid, "elo": elo, "prefs": prefs}
                            best_score = s

                    # Check if match meets ADJUSTED threshold (gets lower over time)
                    if best and best_score >= adjusted_threshold:
                        # Found acceptable match! Create match and return
                        cur.execute("""
                            insert into match_tx (area, user_one_id, user_two_id, compat_score, is_complete)
                            values (%s, %s, %s, %s, false)
                            returning id
                            """, (me_area, me_user, best["user_id"], best_score))
                        match_id = cur.fetchone()[0]

                        cur.execute("update mm_ticket set status='matched' where id=%s", (best["ticket_id"],))
                        cur.execute("delete from mm_ticket where user_id=%s and status='queued'", (me_user,))

                        elapsed = time.time() - start_time
                        return jsonify(
                            matched=True,
                            match_id=str(match_id),
                            compat_score=best_score,
                            wait_time=round(elapsed, 1),
                            attempts=attempt,
                            threshold_used=round(adjusted_threshold, 2)
                        ), 200

        except Exception as e:
            # Log error but continue searching
            print(f"Search attempt {attempt} failed: {e}")
        
        # Wait before next search iteration
        if time.time() - start_time < MATCHMAKING_TIMEOUT:
            time.sleep(MATCHMAKING_POLL_INTERVAL)

    # Timeout reached - close the ticket (keep record of failed attempt)
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                update mm_ticket 
                set status='closed' 
                where user_id=%s and status='queued'
                """, (me_user,))
    
    elapsed = time.time() - start_time
    return jsonify(
        matched=False,
        message="Matchmaking timeout - no suitable opponent found",
        wait_time=round(elapsed, 1),
        attempts=attempt,
        reason="timeout"
    ), 200


@app.post("/match/stream")
def match_stream():
    """
    Server-Sent Events (SSE) matchmaking endpoint.
    
    Streams real-time updates:
    1. Initial: Queue status when joined
    2. Searching: Periodic updates during search
    3. Final: Match result or timeout
    
    Client example:
        const eventSource = new EventSource('/match/stream', {
            method: 'POST',
            body: JSON.stringify({user_id: 'abc123'})
        });
        eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(data.status, data);
        };
    """
    if not pool:
        return jsonify(error="Matchmaking unavailable (no database pool)"), 503
    
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    if not user_id:
        return jsonify(error="Missing user_id"), 400

    def generate():
        start_time = time.time()
        
        # Get user profile and check for existing active matches
        with pool.connection() as conn:
            with conn.cursor() as cur:
                # 1) Check if user already has an active match
                cur.execute("""
                    select id from match_tx
                    where (user_one_id = %s or user_two_id = %s)
                      and is_complete = false
                    limit 1
                    """, (user_id, user_id))
                active_match = cur.fetchone()
                
                if active_match:
                    yield f"data: {json.dumps({'status': 'error', 'error': 'Already in active match', 'active_match_id': str(active_match[0])})}\n\n"
                    return
                
                # 2) Get user profile
                cur.execute("""
                    select u.user_uid as user_id, u.area, u.elo,
                           coalesce(u.preferences, '{}'::jsonb) as prefs
                    from users u
                    where u.user_uid = %s
                    """, (user_id,))
                row = cur.fetchone()
                if not row:
                    yield f"data: {json.dumps({'status': 'error', 'error': 'User not found'})}\n\n"
                    return
                
                me_user, me_area, me_elo, me_prefs = row[0], row[1], row[2], row[3]

                # 3) Get current queue size
                cur.execute("""
                    select count(*) from mm_ticket
                    where status = 'queued' and area = %s
                    """, (me_area,))
                queue_size = cur.fetchone()[0]

        # Queue user immediately with timestamp
        queue_time = time.time()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    insert into mm_ticket (user_id, area, elo, prefs, status, created_at)
                    values (%s, %s, %s, %s, 'queued', NOW())
                    on conflict (user_id) where mm_ticket.status='queued'
                    do update set area=excluded.area, elo=excluded.elo, prefs=excluded.prefs, created_at=NOW()
                    """, (me_user, me_area, me_elo, json.dumps(me_prefs)))

        # Send initial queue event
        yield f"data: {json.dumps({'status': 'queued', 'queue_size': queue_size, 'area': me_area, 'timestamp': time.time()})}\n\n"

        # Keep searching until match found or timeout
        attempt = 0
        while time.time() - start_time < MATCHMAKING_TIMEOUT:
            attempt += 1
            wait_time = time.time() - queue_time
            
            # Calculate adjusted threshold based on time waiting
            adjusted_threshold = max(
                MINIMUM_COMPAT_THRESHOLD,
                INITIAL_COMPAT_THRESHOLD - (wait_time * DECAY_RATE_PER_SECOND)
            )
            
            try:
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        # FIRST: Check if someone else already matched with us
                        cur.execute("""
                            select m.id, m.user_one_id, m.user_two_id, m.compat_score
                            from match_tx m
                            where (m.user_one_id = %s or m.user_two_id = %s)
                              and m.is_complete = false
                            limit 1
                            """, (me_user, me_user))
                        existing_match = cur.fetchone()
                        
                        if existing_match:
                            # We've been matched by another user!
                            match_id, user_one, user_two, compat = existing_match
                            # Clean up our own ticket
                            cur.execute("delete from mm_ticket where user_id=%s and status='queued'", (me_user,))
                            
                            elapsed = time.time() - start_time
                            yield f"data: {json.dumps({'status': 'matched', 'match_id': str(match_id), 'compat_score': compat, 'wait_time': round(elapsed, 1), 'attempts': attempt, 'matched_by': 'opponent'})}\n\n"
                            return
                        
                        # Lock and scan candidates
                        cur.execute("""
                            with c as (
                              select t.id, t.user_id, t.elo, t.prefs, t.created_at
                              from mm_ticket t
                              where t.status = 'queued'
                                and t.area   = %s
                                and t.user_id <> %s
                              order by t.created_at asc
                              limit 50
                              for update skip locked
                            )
                            select id, user_id, elo, prefs from c
                            """, (me_area, me_user))
                        candidates = cur.fetchall()

                        # Find best match
                        best = None
                        best_score = -1
                        for (tid, uid, elo, prefs) in candidates:
                            s = compat_score(me_elo, me_prefs, elo, prefs)
                            if s > best_score:
                                best = {"ticket_id": tid, "user_id": uid, "elo": elo, "prefs": prefs}
                                best_score = s

                        # Send searching update every few attempts
                        if attempt % 3 == 0:  # Every 6 seconds (3 attempts * 2 sec interval)
                            yield f"data: {json.dumps({'status': 'searching', 'attempt': attempt, 'wait_time': round(wait_time, 1), 'threshold': round(adjusted_threshold, 2), 'best_score': round(best_score, 2) if best else None, 'candidates': len(candidates)})}\n\n"

                        # Check if match meets ADJUSTED threshold (gets lower over time)
                        if best and best_score >= adjusted_threshold:
                            # Found acceptable match! Create match and return
                            cur.execute("""
                                insert into match_tx (area, user_one_id, user_two_id, compat_score, is_complete)
                                values (%s, %s, %s, %s, false)
                                returning id
                                """, (me_area, me_user, best["user_id"], best_score))
                            match_id = cur.fetchone()[0]

                            cur.execute("update mm_ticket set status='matched' where id=%s", (best["ticket_id"],))
                            cur.execute("delete from mm_ticket where user_id=%s and status='queued'", (me_user,))

                            elapsed = time.time() - start_time
                            yield f"data: {json.dumps({'status': 'matched', 'match_id': str(match_id), 'compat_score': best_score, 'wait_time': round(elapsed, 1), 'attempts': attempt, 'threshold_used': round(adjusted_threshold, 2)})}\n\n"
                            return

            except Exception as e:
                # Log error but continue searching
                print(f"Search attempt {attempt} failed: {e}")
                yield f"data: {json.dumps({'status': 'searching', 'attempt': attempt, 'error': str(e)})}\n\n"
            
            # Wait before next search iteration
            if time.time() - start_time < MATCHMAKING_TIMEOUT:
                time.sleep(MATCHMAKING_POLL_INTERVAL)

        # Timeout reached - close the ticket (keep record of failed attempt)
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    update mm_ticket 
                    set status='closed' 
                    where user_id=%s and status='queued'
                    """, (me_user,))
        
        elapsed = time.time() - start_time
        yield f"data: {json.dumps({'status': 'timeout', 'message': 'No suitable opponent found', 'wait_time': round(elapsed, 1), 'attempts': attempt})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')








if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)

