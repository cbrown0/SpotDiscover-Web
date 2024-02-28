# use this command to start app: gunicorn -w 4 -b 0.0.0.0:5543 wsgi:app
from main import app

if __name__== '__main__':
    app.run()