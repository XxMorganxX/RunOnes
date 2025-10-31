import os
import sys
import re
from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.supa_db import SupabaseDB

# Create Blueprint for user management
users_bp = Blueprint('users', __name__)

# Initialize database connection
db = SupabaseDB()

# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def validate_username(username: str) -> Tuple[bool, str]:
    """Validate username format"""
    if not username:
        return False, "Username is required"
    
    if len(username) < 3 or len(username) > 20:
        return False, "Username must be 3-20 characters"
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores"
    
    return True, ""

def validate_email(email: str) -> Tuple[bool, str]:
    """Validate email format"""
    if not email:
        return False, "Email is required"
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Invalid email format"
    
    return True, ""

def validate_area(area: str) -> Tuple[bool, str]:
    """Validate area is in allowed list"""
    if not area:
        return False, "Area is required"
    
    valid_areas = ['north', 'south', 'east', 'west', 'central']
    if area not in valid_areas:
        return False, f"Area must be one of: {valid_areas}"
    
    return True, ""

def validate_preferences(prefs: Dict) -> Tuple[bool, str]:
    """Validate user preferences structure"""
    if not isinstance(prefs, dict):
        return False, "Preferences must be a JSON object"
    
    valid_styles = ['aggressive', 'defensive', 'balanced']
    valid_intensities = ['casual', 'medium', 'competitive']
    valid_lengths = ['short', 'medium', 'long']
    
    if 'playing_style' in prefs and prefs['playing_style'] not in valid_styles:
        return False, f"playing_style must be one of: {valid_styles}"
    
    if 'intensity' in prefs and prefs['intensity'] not in valid_intensities:
        return False, f"intensity must be one of: {valid_intensities}"
    
    if 'session_length' in prefs and prefs['session_length'] not in valid_lengths:
        return False, f"session_length must be one of: {valid_lengths}"
    
    if 'communication' in prefs and not isinstance(prefs['communication'], bool):
        return False, "communication must be true or false"
    
    return True, ""

def get_default_preferences() -> Dict:
    """Get default user preferences"""
    return {
        'playing_style': 'balanced',
        'intensity': 'medium',
        'session_length': 'medium',
        'communication': True
    }

def get_default_stats() -> Dict:
    """Get default user statistics"""
    return {
        'total_matches': 0,
        'wins': 0,
        'losses': 0,
        'win_rate': 0.0,
        'current_streak': 0,
        'best_streak': 0
    }

# ============================================================================
# USER CRUD ENDPOINTS
# ============================================================================

@users_bp.route("/users", methods=["POST"])
def create_user():
    """
    Create a new user profile
    
    Required fields: user_uid, username, email, area
    Optional fields: starting_elo, preferences, profile
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body must be JSON'}), 400
        
        # Validate required fields
        required_fields = ['user_uid', 'username', 'email', 'area']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate field formats
        valid, error = validate_username(data['username'])
        if not valid:
            return jsonify({'error': error}), 400
        
        valid, error = validate_email(data['email'])
        if not valid:
            return jsonify({'error': error}), 400
        
        valid, error = validate_area(data['area'])
        if not valid:
            return jsonify({'error': error}), 400
        
        # Validate preferences if provided
        if 'preferences' in data:
            valid, error = validate_preferences(data['preferences'])
            if not valid:
                return jsonify({'error': error}), 400
        
        # Check if user already exists
        existing = db.query_table("users", user_uid=data['user_uid'])
        if existing:
            return jsonify({'error': 'User with this user_uid already exists'}), 409
        
        # Check if username is taken
        username_check = db.query_table("users", username=data['username'])
        if username_check:
            return jsonify({'error': 'Username already taken'}), 409
        
        # Check if email is taken
        email_check = db.query_table("users", email=data['email'])
        if email_check:
            return jsonify({'error': 'Email already registered'}), 409
        
        # Validate starting ELO if provided
        starting_elo = data.get('starting_elo', 1200)
        if not isinstance(starting_elo, int) or starting_elo < 0 or starting_elo > 3000:
            return jsonify({'error': 'starting_elo must be between 0 and 3000'}), 400
        
        # Build user profile
        now = datetime.now().isoformat()
        user_profile = {
            'user_uid': data['user_uid'],
            'username': data['username'],
            'email': data['email'],
            'area': data['area'],
            'elo': starting_elo,
            'preferences': data.get('preferences', get_default_preferences()),
            'stats': get_default_stats(),
            'profile': data.get('profile', {}),
            'created_at': now,
            'updated_at': now,
            'last_active': now,
            'is_active': True
        }
        
        # Create user
        result = db.insert_record("users", user_profile)
        
        return jsonify({
            'message': 'User created successfully',
            'user': result[0]
        }), 201
        
    except Exception as e:
        return jsonify({'error': f'Failed to create user: {str(e)}'}), 500

@users_bp.route("/users/<user_uid>", methods=["GET"])
def get_user(user_uid):
    """Get user profile by user_uid"""
    try:
        user = db.query_table("users", user_uid=user_uid)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Update last_active timestamp
        db.update_by("users", "user_uid", user_uid, {
            'last_active': datetime.now().isoformat()
        })
        
        return jsonify({'user': user[0]}), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch user: {str(e)}'}), 500

@users_bp.route("/users/<user_uid>", methods=["PUT", "PATCH"])
def update_user(user_uid):
    """
    Update user profile
    PUT: Full update, PATCH: Partial update
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body must be JSON'}), 400
        
        # Check if user exists
        existing = db.query_table("users", user_uid=user_uid)
        if not existing:
            return jsonify({'error': 'User not found'}), 404
        
        # Prevent updating protected fields
        protected_fields = ['user_uid', 'elo', 'stats', 'created_at']
        for field in protected_fields:
            if field in data:
                return jsonify({'error': f'Cannot update protected field: {field}'}), 400
        
        # Validate fields if being updated
        if 'username' in data:
            valid, error = validate_username(data['username'])
            if not valid:
                return jsonify({'error': error}), 400
            
            # Check if username is taken by another user
            username_check = db.query_table("users", username=data['username'])
            if username_check and username_check[0]['user_uid'] != user_uid:
                return jsonify({'error': 'Username already taken'}), 409
        
        if 'email' in data:
            valid, error = validate_email(data['email'])
            if not valid:
                return jsonify({'error': error}), 400
            
            # Check if email is taken by another user
            email_check = db.query_table("users", email=data['email'])
            if email_check and email_check[0]['user_uid'] != user_uid:
                return jsonify({'error': 'Email already registered'}), 409
        
        if 'area' in data:
            valid, error = validate_area(data['area'])
            if not valid:
                return jsonify({'error': error}), 400
        
        if 'preferences' in data:
            valid, error = validate_preferences(data['preferences'])
            if not valid:
                return jsonify({'error': error}), 400
        
        # Add updated timestamp
        data['updated_at'] = datetime.now().isoformat()
        
        # Update user
        db.update_by("users", "user_uid", user_uid, data)
        
        # Return updated user
        updated_user = db.query_table("users", user_uid=user_uid)
        return jsonify({
            'message': 'User updated successfully',
            'user': updated_user[0]
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to update user: {str(e)}'}), 500

@users_bp.route("/users/<user_uid>", methods=["DELETE"])
def delete_user(user_uid):
    """
    Delete user profile (soft delete - marks as inactive)
    Prevents deletion if user has active matches
    """
    try:
        # Check if user exists
        existing = db.query_table("users", user_uid=user_uid)
        if not existing:
            return jsonify({'error': 'User not found'}), 404
        
        # Check for active matches
        active_matches = db.client.table("match_tx").select("id").or_(
            f"user_one_id.eq.{user_uid},user_two_id.eq.{user_uid}"
        ).eq("is_complete", False).execute()
        
        if active_matches.data:
            return jsonify({
                'error': 'Cannot delete user with active matches',
                'active_matches': len(active_matches.data),
                'message': 'Complete or cancel active matches first'
            }), 409
        
        # Soft delete (mark as inactive)
        db.update_by("users", "user_uid", user_uid, {
            'is_active': False,
            'updated_at': datetime.now().isoformat()
        })
        
        return jsonify({'message': 'User deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to delete user: {str(e)}'}), 500

@users_bp.route("/users", methods=["GET"])
def list_users():
    """
    List users with optional filtering and pagination
    Query parameters:
    - area: Filter by area
    - min_elo, max_elo: Filter by ELO range
    - active: Filter by active status (default: true)
    - limit: Number of results (default: 50, max: 100)
    - offset: Pagination offset (default: 0)
    - sort: Sort field (default: elo)
    - order: Sort order - asc/desc (default: desc)
    """
    try:
        # Get query parameters
        area = request.args.get('area')
        min_elo = request.args.get('min_elo', type=int)
        max_elo = request.args.get('max_elo', type=int)
        active_only = request.args.get('active', 'true').lower() == 'true'
        limit = min(request.args.get('limit', 50, type=int), 100)  # Cap at 100
        offset = request.args.get('offset', 0, type=int)
        sort_field = request.args.get('sort', 'elo')
        sort_order = request.args.get('order', 'desc')
        
        # Validate sort parameters
        valid_sort_fields = ['elo', 'username', 'created_at', 'updated_at', 'last_active']
        if sort_field not in valid_sort_fields:
            return jsonify({'error': f'Invalid sort field. Must be one of: {valid_sort_fields}'}), 400
        
        if sort_order not in ['asc', 'desc']:
            return jsonify({'error': 'Sort order must be asc or desc'}), 400
        
        # Build query
        query = db.client.table("users").select("*")
        
        # Apply filters
        if area:
            query = query.eq('area', area)
        if min_elo is not None:
            query = query.gte('elo', min_elo)
        if max_elo is not None:
            query = query.lte('elo', max_elo)
        if active_only:
            query = query.eq('is_active', True)
        
        # Apply sorting and pagination
        query = query.order(sort_field, desc=(sort_order == 'desc'))
        query = query.range(offset, offset + limit - 1)
        
        result = query.execute()
        
        return jsonify({
            'users': result.data,
            'count': len(result.data),
            'offset': offset,
            'limit': limit,
            'filters': {
                'area': area,
                'min_elo': min_elo,
                'max_elo': max_elo,
                'active_only': active_only
            },
            'sort': {
                'field': sort_field,
                'order': sort_order
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch users: {str(e)}'}), 500

# ============================================================================
# USER STATISTICS ENDPOINTS
# ============================================================================

@users_bp.route("/users/<user_uid>/stats", methods=["GET"])
def get_user_stats(user_uid):
    """
    Get detailed user statistics including match history
    """
    try:
        # Check if user exists
        user = db.query_table("users", user_uid=user_uid)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        user_data = user[0]
        
        # Get match history
        matches_query = db.client.table("match_tx").select("*").or_(
            f"user_one_id.eq.{user_uid},user_two_id.eq.{user_uid}"
        ).eq("is_complete", True).order('settled_at', desc=True)
        
        matches = matches_query.execute()
        match_data = matches.data
        
        # Calculate statistics
        total_matches = len(match_data)
        wins = len([m for m in match_data if m.get('match_winner') == user_uid])
        losses = total_matches - wins
        win_rate = (wins / total_matches * 100) if total_matches > 0 else 0
        
        # Calculate current win/loss streak
        current_streak = 0
        streak_type = None
        if match_data:
            for match in match_data:
                if match.get('match_winner') == user_uid:
                    if streak_type is None:
                        streak_type = 'win'
                    if streak_type == 'win':
                        current_streak += 1
                    else:
                        break
                elif match.get('match_winner') is not None:  # Loss (not cancelled)
                    if streak_type is None:
                        streak_type = 'loss'
                    if streak_type == 'loss':
                        current_streak += 1
                    else:
                        break
        
        # Calculate best win streak
        best_win_streak = 0
        current_win_streak = 0
        for match in reversed(match_data):  # Go chronologically
            if match.get('match_winner') == user_uid:
                current_win_streak += 1
                best_win_streak = max(best_win_streak, current_win_streak)
            elif match.get('match_winner') is not None:
                current_win_streak = 0
        
        # ELO progression (last 10 matches)
        recent_matches = match_data[:10]
        
        # Calculate average opponent ELO
        opponent_elos = []
        for match in match_data:
            if match['user_one_id'] == user_uid:
                # Get user_two's ELO at time of match
                opponent_elo = match.get('user_two_elo') or (user_data['elo'] - match.get('elo_diff', 0))
            else:
                # Get user_one's ELO at time of match  
                opponent_elo = match.get('user_one_elo') or (user_data['elo'] + match.get('elo_diff', 0))
            
            if opponent_elo:
                opponent_elos.append(opponent_elo)
        
        avg_opponent_elo = sum(opponent_elos) / len(opponent_elos) if opponent_elos else user_data['elo']
        
        return jsonify({
            'user_uid': user_uid,
            'username': user_data['username'],
            'current_elo': user_data['elo'],
            'area': user_data['area'],
            'account_age_days': (datetime.now() - datetime.fromisoformat(user_data['created_at'].replace('Z', '+00:00'))).days,
            'statistics': {
                'total_matches': total_matches,
                'wins': wins,
                'losses': losses,
                'win_rate': round(win_rate, 1),
                'current_streak': {
                    'count': current_streak,
                    'type': streak_type or 'none'
                },
                'best_win_streak': best_win_streak,
                'average_opponent_elo': round(avg_opponent_elo, 0)
            },
            'recent_matches': recent_matches,
            'last_active': user_data['last_active']
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch user stats: {str(e)}'}), 500

@users_bp.route("/users/<user_uid>/matches", methods=["GET"])
def get_user_matches(user_uid):
    """
    Get user's match history with pagination
    Query parameters:
    - limit: Number of matches (default: 20, max: 100)
    - offset: Pagination offset (default: 0)
    - completed_only: Show only completed matches (default: true)
    """
    try:
        # Check if user exists
        user = db.query_table("users", user_uid=user_uid)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Get query parameters
        limit = min(request.args.get('limit', 20, type=int), 100)
        offset = request.args.get('offset', 0, type=int)
        completed_only = request.args.get('completed_only', 'true').lower() == 'true'
        
        # Build query
        query = db.client.table("match_tx").select("*").or_(
            f"user_one_id.eq.{user_uid},user_two_id.eq.{user_uid}"
        )
        
        if completed_only:
            query = query.eq("is_complete", True)
        
        query = query.order('created_at', desc=True).range(offset, offset + limit - 1)
        
        result = query.execute()
        
        # Enhance matches with opponent info
        enhanced_matches = []
        for match in result.data:
            opponent_id = match['user_two_id'] if match['user_one_id'] == user_uid else match['user_one_id']
            opponent = db.query_table("users", user_uid=opponent_id)
            
            enhanced_match = {
                **match,
                'opponent': {
                    'user_uid': opponent_id,
                    'username': opponent[0]['username'] if opponent else 'Unknown',
                    'elo': opponent[0]['elo'] if opponent else None
                },
                'user_won': match.get('match_winner') == user_uid,
                'user_score': match.get('score', {}).get(user_uid, 0),
                'opponent_score': match.get('score', {}).get(opponent_id, 0)
            }
            enhanced_matches.append(enhanced_match)
        
        return jsonify({
            'matches': enhanced_matches,
            'count': len(enhanced_matches),
            'offset': offset,
            'limit': limit,
            'user_uid': user_uid
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch user matches: {str(e)}'}), 500

# ============================================================================
# LEADERBOARD ENDPOINT
# ============================================================================

@users_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    """
    Get leaderboard with top players
    Query parameters:
    - area: Filter by area (optional)
    - limit: Number of players (default: 50, max: 100)
    - min_matches: Minimum matches to be included (default: 5)
    """
    try:
        # Get query parameters
        area = request.args.get('area')
        limit = min(request.args.get('limit', 50, type=int), 100)
        min_matches = request.args.get('min_matches', 5, type=int)
        
        # Build base query for active users
        query = db.client.table("users").select("*").eq('is_active', True)
        
        if area:
            query = query.eq('area', area)
        
        # For now, assume users have a total_matches field in stats
        # In a real implementation, you'd join with match history
        query = query.order('elo', desc=True).limit(limit)
        
        result = query.execute()
        
        # Filter by minimum matches and add ranking
        leaderboard = []
        rank = 1
        for user in result.data:
            user_stats = user.get('stats', {})
            total_matches = user_stats.get('total_matches', 0)
            
            if total_matches >= min_matches:
                leaderboard_entry = {
                    'rank': rank,
                    'user_uid': user['user_uid'],
                    'username': user['username'],
                    'elo': user['elo'],
                    'area': user['area'],
                    'total_matches': total_matches,
                    'wins': user_stats.get('wins', 0),
                    'losses': user_stats.get('losses', 0),
                    'win_rate': user_stats.get('win_rate', 0),
                    'current_streak': user_stats.get('current_streak', 0)
                }
                leaderboard.append(leaderboard_entry)
                rank += 1
        
        return jsonify({
            'leaderboard': leaderboard,
            'filters': {
                'area': area,
                'min_matches': min_matches
            },
            'total_players': len(leaderboard)
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to fetch leaderboard: {str(e)}'}), 500

# ============================================================================
# HEALTH CHECK
# ============================================================================

@users_bp.route("/users/health", methods=["GET"])
def users_health():
    """Health check for user management module"""
    try:
        # Test database connection
        test_query = db.client.table("users").select("count").limit(1).execute()
        
        return jsonify({
            'status': 'healthy',
            'module': 'user_management',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'module': 'user_management', 
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500