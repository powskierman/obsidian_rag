#!/usr/bin/env python3
"""
Query Feedback System for Self-Improving RAG
Tracks query metrics and user feedback to enable learning and improvement
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
import threading

# Create feedback database directory if it doesn't exist
FEEDBACK_DB_DIR = Path("./feedback_db")
FEEDBACK_DB_DIR.mkdir(exist_ok=True)

DB_PATH = FEEDBACK_DB_DIR / "query_feedback.db"
METRICS_PATH = FEEDBACK_DB_DIR / "metrics.json"

# Thread lock for database access
db_lock = threading.Lock()

def init_database():
    """Initialize the feedback database with required tables"""
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Query metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS query_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_text TEXT NOT NULL,
                mode TEXT DEFAULT 'vector',
                num_results INTEGER,
                avg_score REAL,
                latency_ms REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_rating INTEGER,
                feedback_text TEXT
            )
        ''')

        # Query performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS query_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL,
                avg_latency_ms REAL,
                success_rate REAL,
                total_queries INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()


def log_query(query_text, mode='vector', num_results=5, avg_score=0.0, latency_ms=0.0):
    """
    Log a query with its metrics

    Args:
        query_text: The original query text
        mode: Retrieval mode (vector, graph-naive, graph-local, etc.)
        num_results: Number of results returned
        avg_score: Average relevance score of results
        latency_ms: Query latency in milliseconds

    Returns:
        query_id: Database ID of the logged query
    """
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO query_metrics
            (query_text, mode, num_results, avg_score, latency_ms)
            VALUES (?, ?, ?, ?, ?)
        ''', (query_text, mode, num_results, avg_score, latency_ms))

        query_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return query_id


def save_feedback(query_id, user_rating, feedback_text=""):
    """
    Save user feedback for a query

    Args:
        query_id: Database ID of the query
        user_rating: Rating from 1-5 (or 0 for no rating)
        feedback_text: Optional text feedback
    """
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE query_metrics
            SET user_rating = ?, feedback_text = ?
            WHERE id = ?
        ''', (user_rating, feedback_text, query_id))

        conn.commit()
        conn.close()


def get_metrics(hours=24):
    """
    Get query metrics for the last N hours

    Returns:
        dict: Aggregated metrics
    """
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cutoff_time = datetime.now() - timedelta(hours=hours)

        # Total queries
        cursor.execute('''
            SELECT COUNT(*) FROM query_metrics
            WHERE timestamp > ?
        ''', (cutoff_time.isoformat(),))
        total_queries = cursor.fetchone()[0]

        # Queries with feedback
        cursor.execute('''
            SELECT COUNT(*) FROM query_metrics
            WHERE timestamp > ? AND user_rating IS NOT NULL
        ''', (cutoff_time.isoformat(),))
        feedback_count = cursor.fetchone()[0]

        # Average rating
        cursor.execute('''
            SELECT AVG(user_rating) FROM query_metrics
            WHERE timestamp > ? AND user_rating IS NOT NULL
        ''', (cutoff_time.isoformat(),))
        avg_rating = cursor.fetchone()[0] or 0.0

        # Average latency per mode
        cursor.execute('''
            SELECT mode, AVG(latency_ms), COUNT(*)
            FROM query_metrics
            WHERE timestamp > ?
            GROUP BY mode
        ''', (cutoff_time.isoformat(),))
        mode_stats = {row[0]: {'avg_latency': row[1], 'count': row[2]} for row in cursor.fetchall()}

        # Success rate (rating >= 4)
        cursor.execute('''
            SELECT COUNT(*) FROM query_metrics
            WHERE timestamp > ? AND user_rating >= 4
        ''', (cutoff_time.isoformat(),))
        success_count = cursor.fetchone()[0]
        success_rate = (success_count / feedback_count * 100) if feedback_count > 0 else 0.0

        conn.close()

        return {
            'total_queries': total_queries,
            'feedback_count': feedback_count,
            'feedback_rate': (feedback_count / total_queries * 100) if total_queries > 0 else 0.0,
            'avg_rating': round(avg_rating, 2),
            'success_rate': round(success_rate, 1),
            'mode_stats': mode_stats,
            'time_period_hours': hours
        }


def get_mode_performance(mode):
    """
    Get performance statistics for a specific retrieval mode

    Returns:
        dict: Performance metrics for the mode
    """
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Average latency
        cursor.execute('''
            SELECT AVG(latency_ms) FROM query_metrics WHERE mode = ?
        ''', (mode,))
        avg_latency = cursor.fetchone()[0] or 0.0

        # Total uses
        cursor.execute('''
            SELECT COUNT(*) FROM query_metrics WHERE mode = ?
        ''', (mode,))
        total_uses = cursor.fetchone()[0]

        # Success rate (rating >= 4)
        cursor.execute('''
            SELECT COUNT(*) FROM query_metrics
            WHERE mode = ? AND user_rating >= 4
        ''', (mode,))
        success_count = cursor.fetchone()[0]
        success_rate = (success_count / total_uses * 100) if total_uses > 0 else 0.0

        # Average score
        cursor.execute('''
            SELECT AVG(avg_score) FROM query_metrics WHERE mode = ?
        ''', (mode,))
        avg_score = cursor.fetchone()[0] or 0.0

        conn.close()

        return {
            'mode': mode,
            'avg_latency_ms': round(avg_latency, 2),
            'total_uses': total_uses,
            'success_rate': round(success_rate, 1),
            'avg_relevance_score': round(avg_score, 3)
        }


def get_all_mode_performance():
    """Get performance stats for all modes"""
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT DISTINCT mode FROM query_metrics')
        modes = [row[0] for row in cursor.fetchall()]
        conn.close()

    return [get_mode_performance(mode) for mode in modes]


def get_low_performing_queries(threshold_rating=2, limit=10):
    """
    Get queries that received low ratings
    Useful for identifying areas of improvement

    Returns:
        list: Low-performing queries
    """
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, query_text, mode, user_rating, feedback_text, timestamp
            FROM query_metrics
            WHERE user_rating IS NOT NULL AND user_rating <= ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (threshold_rating, limit))

        results = cursor.fetchall()
        conn.close()

    return [{
        'id': row[0],
        'query': row[1],
        'mode': row[2],
        'rating': row[3],
        'feedback': row[4],
        'timestamp': row[5]
    } for row in results]


def get_high_performing_queries(threshold_rating=4, limit=10):
    """
    Get queries that received high ratings
    Useful for understanding what works well

    Returns:
        list: High-performing queries
    """
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, query_text, mode, user_rating, timestamp
            FROM query_metrics
            WHERE user_rating IS NOT NULL AND user_rating >= ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (threshold_rating, limit))

        results = cursor.fetchall()
        conn.close()

    return [{
        'id': row[0],
        'query': row[1],
        'mode': row[2],
        'rating': row[3],
        'timestamp': row[4]
    } for row in results]


def export_metrics(output_file=None):
    """
    Export all metrics to JSON for analysis

    Args:
        output_file: Path to export to (default: metrics.json)
    """
    if output_file is None:
        output_file = METRICS_PATH

    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM query_metrics ORDER BY timestamp DESC LIMIT 1000')
        columns = [description[0] for description in cursor.description]
        results = cursor.fetchall()
        conn.close()

    metrics_data = [dict(zip(columns, row)) for row in results]

    with open(output_file, 'w') as f:
        json.dump(metrics_data, f, indent=2, default=str)

    return str(output_file)


def get_database_stats():
    """Get overall database statistics"""
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM query_metrics')
        total_metrics = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM query_metrics WHERE user_rating IS NOT NULL')
        total_feedback = cursor.fetchone()[0]

        cursor.execute('SELECT MIN(timestamp) FROM query_metrics')
        first_query = cursor.fetchone()[0]

        cursor.execute('SELECT MAX(timestamp) FROM query_metrics')
        last_query = cursor.fetchone()[0]

        conn.close()

    return {
        'total_queries_logged': total_metrics,
        'total_feedback_given': total_feedback,
        'first_query': first_query,
        'last_query': last_query
    }


# Initialize database on import
init_database()
