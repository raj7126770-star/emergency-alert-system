"""Development entry point for the We Care 24x7 Flask application."""

from backend.app import app


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
