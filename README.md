# Sports ELO Matchmaking System

A Flask-based matchmaking API that pairs players using ELO ratings and compatibility scoring. The system features real-time matchmaking with dynamic threshold adjustments, match management, and automatic ELO rating updates.

## What It Does

This project provides a complete matchmaking infrastructure for competitive 1v1 games or sports:

- **ELO Rating System**: Tracks player skill levels using the standard ELO algorithm
- **Smart Matchmaking**: Pairs players based on ELO proximity and custom preferences
- **Dynamic Compatibility**: Gradually relaxes matching requirements to reduce wait times
- **Match Management**: Handles match creation, cancellation, and completion with atomic transactions
- **Real-time Updates**: Server-Sent Events (SSE) for live matchmaking status
- **Dual Database Approach**: Uses both Supabase for CRUD operations and PostgreSQL connection pools for high-performance matchmaking with row-level locking

## Purpose

The system is designed to:

1. **Fair Matchmaking**: Ensure players are matched with opponents of similar skill levels
2. **Reduce Wait Times**: Automatically adjust matching criteria the longer a player waits
3. **Prevent Race Conditions**: Use database row locking to avoid duplicate matches
4. **Track Player Progress**: Automatically update ELO ratings after each match
5. **Scale Efficiently**: Handle multiple concurrent matchmaking requests with connection pooling

## Project Structure

```
ones_elo/
├── config/
│   └── config.py              # Configuration settings (database, matchmaking parameters)
├── core/
│   ├── app.py                 # Flask REST API server with matchmaking endpoints
│   └── supa_db.py             # Supabase database client wrapper
├── utils/
│   ├── elo.py                 # ELO rating calculation algorithms
│   └── mm_logic.py            # Matchmaking compatibility scoring logic
├── UI/
│   └── sports_elo_gui.py      # Simple Tkinter GUI (demo interface)
└── requirements.txt           # Python dependencies
```

## Key Features

### Matchmaking Endpoints

- **POST /match**: Blocking matchmaking (returns when match found or timeout)
- **POST /match/stream**: Server-Sent Events streaming for real-time updates
- **POST /match/start**: Create a new match between two players
- **POST /match/finish**: Complete a match and update ELO ratings
- **GET /match/cancel/<match_id>**: Cancel an active match

### Matchmaking Algorithm

1. Player enters queue with their ELO and preferences
2. System searches for compatible opponents in the same area
3. Compatibility threshold starts high (8.0/10) and gradually decreases
4. Best match is selected when threshold is met
5. Match is created atomically to prevent race conditions
6. Failed matches timeout after 60 seconds

### ELO System

- Standard ELO formula with K-factor of 32
- Automatic rating updates after match completion
- Expected score calculation based on rating difference
- Transaction-safe updates to prevent rating corruption

## How to Run

### Prerequisites

- Python 3.8+
- PostgreSQL database
- Supabase account (or PostgreSQL with REST API)

### Installation

1. **Clone the repository** (or navigate to the project directory):
   ```bash
   cd ones_elo
   ```

2. **Create and activate virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   # or
   venv\Scripts\activate     # On Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   Create a `.env` file in the project root with:
   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_anon_key
   DATABASE_URL=postgresql://user:password@host:port/database
   ```

5. **Set up database tables**:
   You'll need the following tables in your database:
   - `users` - Player profiles with ELO ratings
   - `match_tx` - Match transaction history
   - `mm_ticket` - Matchmaking queue tickets

### Running the Server

1. **Start the Flask API server**:
   ```bash
   python core/app.py
   ```
   The server will run on `http://0.0.0.0:8000`

2. **Test the health endpoint**:
   ```bash
   curl http://localhost:8000/api/health
   ```

3. **(Optional) Run the GUI**:
   ```bash
   python UI/sports_elo_gui.py
   ```

### Example API Usage

**Start matchmaking:**
```bash
curl -X POST http://localhost:8000/match \
  -H "Content-Type: application/json" \
  -d '{"user_id": "player123"}'
```

**Stream matchmaking updates:**
```bash
curl -X POST http://localhost:8000/match/stream \
  -H "Content-Type: application/json" \
  -d '{"user_id": "player123"}'
```

**Finish a match:**
```bash
curl -X POST http://localhost:8000/match/finish \
  -H "Content-Type: application/json" \
  -d '{
    "match_id": 42,
    "score": [11, 5]
  }'
```

## Configuration

Key parameters in `config/config.py`:

- `MATCHMAKING_TIMEOUT`: Maximum wait time (default: 60 seconds)
- `INITIAL_COMPAT_THRESHOLD`: Starting compatibility requirement (default: 8.0/10)
- `MINIMUM_COMPAT_THRESHOLD`: Minimum threshold after decay (default: 3.0/10)
- `DECAY_RATE_PER_SECOND`: How fast threshold decreases (default: 0.05/second)
- `MATCHMAKING_POLL_INTERVAL`: How often to search for matches (default: 2 seconds)

## License

This project is provided as-is for educational and development purposes.

