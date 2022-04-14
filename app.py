# to porwer the server functions 
from flask import Flask, jsonify, request, make_response # flask server
import pickle # read the model
from flask_sqlalchemy import SQLAlchemy # communicate with sqlite3 database
from werkzeug.security import generate_password_hash, check_password_hash # generate pass_hash
from flask_limiter import Limiter # limit requests to server
from flask_limiter.util import get_remote_address

# genral libraries
import uuid
import jwt
import datetime
from functools import wraps

# get the list of features used by our model
from features import FEATURES

# get ngrok
from flask_ngrok import run_with_ngrok

# load the .pkl model
MODEL = pickle.load(open('models/best_model.pkl', 'rb'))

# define the app 
app = Flask(__name__)

# setup app variables 
app.config['SECRET_KEY']='Th1s1ss3cr3t'
app.config['SQLALCHEMY_DATABASE_URI']='sqlite://///home/jose/Documents/CAPSTONE/model_api/db/access_control.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True

# define db object
db = SQLAlchemy(app)

# define limiter
limiter = Limiter(
    run_with_ngrok(app), # start the app using ngrok address
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Create tables
class Users(db.Model):
     id = db.Column(db.Integer, primary_key=True)
     public_id = db.Column(db.Integer)
     name = db.Column(db.String(50))
     password = db.Column(db.String(50))
     admin = db.Column(db.Boolean)

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        token = None
        # ensure the jwt-token is passed with the headers
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']
        if not token: # throw error if no token provided
            return make_response(jsonify({"message": "A valid token is missing!"}), 401)
        try:
           # decode the token to obtain user public_id
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = Users.query.filter_by(public_id=data['public_id']).first()
        except:
            return make_response(jsonify({"message": "Invalid token!"}), 401)
         # Return the user information attached to the token
        return f(*args, **kwargs)
    return decorator

# register user
@app.route('/register', methods=['POST'])
def signup_user(): 
   data = request.get_json() 
   hashed_password = generate_password_hash(data['password'], method='sha256')
 
   new_user = Users(public_id=str(uuid.uuid4()), name=data['name'], password=hashed_password, admin=False)
   db.session.add(new_user) 
   db.session.commit()   
   return jsonify({'message': 'registered successfully'})

# login 
@app.route('/login', methods=['GET', 'POST'])  
def login_user():

   auth = request.authorization 
   user = Users.query.filter_by(name=auth.username).first()
   if not auth or not auth.username or not auth.password or user==None: 
       return make_response('could not verify', 401, {'Authentication': 'login required"'})   
 
   if check_password_hash(user.password, auth.password):
       token = jwt.encode({'public_id' : user.public_id, 'exp' : datetime.datetime.utcnow() + datetime.timedelta(minutes=45)}, app.config['SECRET_KEY'], "HS256")
 
       return jsonify({'token' : token})
 
   return make_response('could not verify',  401, {'Authentication': '"login required"'})

# get list of all users registered
@app.route('/user', methods=['GET'])
def get_all_users(): 
 
   users = Users.query.all()
   result = []  
   for user in users:  
       user_data = {}  
       user_data['public_id'] = user.public_id 
       user_data['name'] = user.name
       user_data['password'] = user.password
       user_data['admin'] = user.admin
     
       result.append(user_data)  
   return jsonify({'users': result})

# submit input to the model and get result
@app.route('/api', methods=['GET'])
@limiter.limit("200 per day")
@token_required 
def api():
    """Handle request and output model score in json format."""
    # Handle empty requests.
    if not request.json:
        return jsonify({'error': 'input is not a json file'})

    # Parse request args into feature array for prediction.
    x_list, missing_data = parse_args(request.json)
    x_array = [x_list]
    
    # Check if there are missing values in user input
    if missing_data == True:
        return jsonify({'error': 'Your Input Contains Invalid or Missing Values'})
    
    else:
        # Predict on x_array and return JSON response.
        estimate = float(MODEL.predict(x_array)[0])
        app_nature = 'Malicious'
        
        # Tell if predicted values is equal to M or B application  
        if estimate > 0.5:
            app_nature = 'Benign'
            
        
        # Responde dictionary
        dict_resp = {'ACURRACY': '91%', 'RESULT' : app_nature}

        response = dict(dict_resp)
        return jsonify(response)

# api subfunction to convert input to valid list of values
def parse_args(request_dict):
    """Parse model features from incoming requests formatted in JSON."""
    # Initialize missing_data as False.
    missing_data = False

    # Parse out the features from the request_dict.
    x_list = []
    for feature in FEATURES:
        value = request_dict.get(feature,)
        if value in [0, 1]:
            x_list.append(value)
        else:
            # Handle missing features.
            x_list.append(0)
            missing_data = True
    return x_list, missing_data

# main to run the app
if __name__ == '__main__':
    app.run()
