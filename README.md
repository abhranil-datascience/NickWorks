# This repository will contain all the projects done for Nicholas.
## Project 1: Hello World secured by Json Web token
This is a sample Hello World project which is secured by Json Web token. There are two endpoints as mentioned below. To execute sayHello endpoint we have to first get a token using the getToken method. The token is valid till 30 seconds (we can change it as per need). Now using the token we can hit sayHello to get the correct response. The endpoint sayHello will not work without the token, thus restricting unauthorized hackers to access it.
