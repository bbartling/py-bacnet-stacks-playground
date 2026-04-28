from app.app import app
from app.config import settings

if __name__ == '__main__':
    app.run(host=settings.bind, port=settings.port, debug=settings.flask_debug, threaded=True)
