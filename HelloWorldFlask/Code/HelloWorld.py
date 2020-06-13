from flask import Flask, jsonify, request
from flask_restful import Resource, Api

# creating the flask app
app = Flask(__name__)

# creating an API object
api = Api(app)

# making a class for a particular resource
# the get, post methods correspond to get and post requests
# they are automatically mapped by flask_restful.
# other methods include put, delete, etc.
class Hello(Resource):
    def post(self):
        data = request.get_json()     # status code
        name = data['name']
        return {'message': 'Hello '+name}, 201

# adding the defined resources along with their corresponding urls
api.add_resource(Hello, '/sayHello')

# driver function
if __name__ == '__main__':
    app.run(debug = True)
