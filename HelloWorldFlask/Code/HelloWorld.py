from flask import Flask, jsonify, request
from flask_restful import Resource, Api
from flask_jwt_extended import JWTManager,create_access_token,jwt_required
import os,random,datetime

# creating the flask app
app = Flask(__name__)
app.config['JWT_SECRET_KEY']=os.getenv('JWT_SECRET_KEY')
# creating an API object
api = Api(app)
jwt = JWTManager(app)

# making a class for a particular resource
# the get, post methods correspond to get and post requests
# they are automatically mapped by flask_restful.
# other methods include put, delete, etc.
################################### Create Token ####################################################
class GetToken(Resource):
    def get(self):
        expires = datetime.timedelta(seconds=30)
        return {'token':create_access_token(identity=str(random.randint(10000,99999)), expires_delta=expires)}
################################### Greet User secured by Json Web Token ####################################################
class Hello(Resource):
    @jwt_required
    def post(self):
        data = request.get_json()     # status code
        name = data['name']
        return {'message': 'Hello '+name}, 201
#################### adding the defined resources along with their corresponding urls #################
api.add_resource(GetToken, '/getToken')
api.add_resource(Hello, '/sayHello')
# driver function
if __name__ == '__main__':
    app.run(debug = True)
