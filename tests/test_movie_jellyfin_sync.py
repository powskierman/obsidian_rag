from pathlib import Path

from src.movies.jellyfin_sync import (
    JellyfinMovie,
    _normalize_base_url,
    _auth_header_value,
    match_note_to_movie,
    update_note_frontmatter,
    _build_movie_indexes,
)


def test_normalize_base_url_accepts_web_ui_url():
    assert _normalize_base_url("http://192.168.2.238:8096/web/index.html") == "http://192.168.2.238:8096"


def test_auth_header_value_can_embed_token():
    header = _auth_header_value(token="abc123")
    assert header.startswith("MediaBrowser ")
    assert 'Token="abc123"' in header


def test_match_note_to_movie_prefers_title_year():
    movie = JellyfinMovie(
        item_id="abc123",
        title="Fall of the Roman Empire",
        year=1964,
        path="/media/movies/Fall of the Roman Empire/Fall of the Roman Empire.m4v",
        imdb_id="tt0058085",
        tmdb_id="123",
        directors=["Anthony Mann"],
        genres=["Drama", "History"],
        runtime_min=188,
        content_rating="PG-13",
        imdb_rating=6.7,
        overview="Roman empire epic.",
    )
    indexes = _build_movie_indexes([movie])
    frontmatter = {
        "kind": "movie",
        "title": "Fall of the Roman Empire",
        "year": 1964,
        "provenance": "NAS",
    }

    match = match_note_to_movie(Path("Media/Movies/Fall of the Roman Empire.md"), frontmatter, indexes)

    assert match is not None
    assert match.reason == "title+year"
    assert match.movie.item_id == "abc123"


def test_update_note_frontmatter_backfills_blank_fields_and_preserves_user_fields():
    movie = JellyfinMovie(
        item_id="abc123",
        title="Fall of the Roman Empire",
        year=1964,
        path="/media/movies/Fall of the Roman Empire/Fall of the Roman Empire.m4v",
        imdb_id="tt0058085",
        tmdb_id="123",
        directors=["Anthony Mann"],
        genres=["Drama", "History"],
        runtime_min=188,
        content_rating="PG-13",
        imdb_rating=6.7,
        overview="Roman empire epic.",
    )
    frontmatter = {
        "id": "mov-fall-of-the-roman-empire-1964",
        "kind": "movie",
        "title": "Fall of the Roman Empire",
        "year": 1964,
        "imdb_id": None,
        "tmdb_id": "",
        "director": None,
        "genre": [],
        "runtime_min": None,
        "content_rating": None,
        "imdb_rating": None,
        "your_rating": 4.5,
        "watched": True,
        "provenance": "NAS",
    }

    updated, changes = update_note_frontmatter(
        frontmatter,
        movie,
        base_url="http://192.168.2.238:8096",
    )

    assert updated["imdb_id"] == "tt0058085"
    assert updated["tmdb_id"] == "123"
    assert updated["director"] == "Anthony Mann"
    assert updated["genre"] == ["Drama", "History"]
    assert updated["runtime_min"] == 188
    assert updated["content_rating"] == "PG-13"
    assert updated["imdb_rating"] == 6.7
    assert updated["jellyfin_item_id"] == "abc123"
    assert updated["jellyfin_path"] == "/media/movies/Fall of the Roman Empire/Fall of the Roman Empire.m4v"
    assert updated["jellyfin_url"] == "http://192.168.2.238:8096/web/index.html#!/details?id=abc123"
    assert updated["your_rating"] == 4.5
    assert updated["watched"] is True
    assert "imdb_id" in changes
    assert "jellyfin_item_id" in changes


def test_update_note_frontmatter_does_not_overwrite_existing_metadata():
    movie = JellyfinMovie(
        item_id="abc123",
        title="Fall of the Roman Empire",
        year=1964,
        path="/media/movies/Fall of the Roman Empire/Fall of the Roman Empire.m4v",
        imdb_id="tt0058085",
        tmdb_id="123",
        directors=["Anthony Mann"],
        genres=["Drama", "History"],
        runtime_min=188,
        content_rating="PG-13",
        imdb_rating=6.7,
        overview="Roman empire epic.",
    )
    frontmatter = {
        "kind": "movie",
        "title": "Fall of the Roman Empire",
        "year": 1964,
        "imdb_id": "tt0000001",
        "director": "Existing Director",
        "genre": ["Existing Genre"],
        "runtime_min": 100,
        "provenance": "NAS",
    }

    updated, changes = update_note_frontmatter(
        frontmatter,
        movie,
        base_url="http://192.168.2.238:8096",
    )

    assert updated["imdb_id"] == "tt0000001"
    assert updated["director"] == "Existing Director"
    assert updated["genre"] == ["Existing Genre"]
    assert updated["runtime_min"] == 100
    assert "imdb_id" not in changes
    assert "director" not in changes
    assert "genre" not in changes
    assert "runtime_min" not in changes


def test_match_note_to_movie_handles_articles_and_path_aliases():
    movie = JellyfinMovie(
        item_id="abc123",
        title="The Fall of the Roman Empire",
        year=1964,
        path="/media/movies/Fall of the Roman Empire/Fall of the Roman Empire.m4v",
        imdb_id="tt0058085",
        tmdb_id="17277",
        directors=["Anthony Mann"],
        genres=["Drama", "History"],
        runtime_min=188,
        content_rating="PG-13",
        imdb_rating=6.7,
        overview="Roman empire epic.",
    )
    indexes = _build_movie_indexes([movie])
    frontmatter = {
        "kind": "movie",
        "title": "Fall of the Roman Empire",
        "year": 1964,
        "provenance": "NAS",
    }

    match = match_note_to_movie(Path("Media/Movies/Fall of the Roman Empire.md"), frontmatter, indexes)

    assert match is not None
    assert match.reason == "title+year"


def test_match_note_to_movie_handles_duplicate_items_with_same_provider_ids():
    movie_a = JellyfinMovie(
        item_id="a",
        title="E.T. the Extra-Terrestrial",
        year=1982,
        path="/media/movies/E.T., The Extra-Terrestrial (1982)/E.T., The Extra-Terrestrial (1982).mp4",
        imdb_id="tt0083866",
        tmdb_id="601",
        directors=["Steven Spielberg"],
        genres=["Sci-Fi"],
        runtime_min=115,
        content_rating="PG",
        imdb_rating=7.9,
        overview="Alien story.",
    )
    movie_b = JellyfinMovie(
        item_id="b",
        title="E.T. the Extra-Terrestrial",
        year=1982,
        path="/media/movies/E.t. The Extra-terrestrial (1982)/E.t. The Extra-terrestrial (1982).m4v",
        imdb_id="tt0083866",
        tmdb_id="601",
        directors=["Steven Spielberg"],
        genres=["Sci-Fi"],
        runtime_min=115,
        content_rating="PG",
        imdb_rating=7.9,
        overview="Alien story.",
    )
    indexes = _build_movie_indexes([movie_a, movie_b])
    frontmatter = {
        "kind": "movie",
        "title": "E.t. The Extra-terrestrial",
        "year": 1982,
        "provenance": "NAS",
    }

    match = match_note_to_movie(Path("Media/Movies/E.t. The Extra-terrestrial.md"), frontmatter, indexes)

    assert match is not None
    assert match.reason == "title+year"
    assert match.movie.imdb_id == "tt0083866"
