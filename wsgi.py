import os

from app import create_app
from flask_cors import CORS
config_name = os.getenv('APP_SETTINGS') # config_name = "development"
app = create_app(config_name)
CORS(app)
if __name__ == '__main__':
    app.run(host='0.0.0.0')
