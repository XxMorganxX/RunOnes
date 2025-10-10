import os
from dotenv import load_dotenv


load_dotenv()

# PostgreSQL direct connection string (for connection pooling)
DB_DSN = os.getenv("DATABASE_URL") 

# Supabase REST API URL (used by SupabaseDB client)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Matchmaking configuration - Ticket Age + Compatibility Decay
BASE_ETA_SECONDS = 20
MATCHMAKING_TIMEOUT = 120  # Max seconds to search before giving up (2 minutes)
MATCHMAKING_POLL_INTERVAL = 2  # Check for new opponents every 2 seconds

# Compatibility decay settings (1-10 scale)
INITIAL_COMPAT_THRESHOLD = 9.0  # Start very picky (need 8/10 match)
MINIMUM_COMPAT_THRESHOLD = 3.0  # Eventually accept 3/10 match
DECAY_RATE_PER_SECOND = 0.05  # Threshold drops by 0.05 per second waiting