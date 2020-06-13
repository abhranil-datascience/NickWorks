from flask import Flask, jsonify, request
from flask_restful import Resource, Api
from flask_jwt_extended import JWTManager,create_access_token,jwt_required
import os,random,datetime,fitz,cv2,io
from PIL import Image
import pytesseract as pt
from google.cloud import vision
from google.cloud.vision import types
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
################################# Check File Validity ################################################
######### OCR using Tesseract ##########
class CheckFileValidityTesseract(Resource):
    @jwt_required
    def post(self):
        data = request.get_json()
        num_of_matches = data['number_of_matches']
        IdentifierList=['western australia','death certificate','registration number','certificate number','deceased','surname',' given names',
                        'place of death','date of death','occupation & sex','age & date of birth','usual address','place of birth',"mother's surname",
                        'maiden surname','given names','usual occupation',"father's surname",'maritial status',"de facto partner's name",'cause of death']
        dataset_dir = os.listdir('../Dataset')
        image_file_dir = os.listdir('../Images')
        FileAnalysis={}
        ################ Read Each File and Change to png format ####################
        for file in dataset_dir:
            current_file="../Dataset/"+file
            count=1
            if file.endswith('.pdf'):
                doc = fitz.open(current_file)
                for i in range(len(doc)):
                    for img in doc.getPageImageList(i):
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n < 5:       # this is GRAY or RGB
                            pix.writePNG("../Images/Image"+str(count)+".png")
                            count=count+1
                        else:               # CMYK: convert to RGB first
                            pix1 = fitz.Pixmap(fitz.csRGB, pix)
                            pix1.writePNG("../Images/Image"+str(count)+".png")
                            count=count+1
                            pix1 = None
                        pix = None
            else:
                im = Image.open(current_file)
                im.save('../Images/Image'+str(count)+".png")
            ################ Perform OCR ####################
            ImageToText=""
            for image_files in os.listdir('../Images'):
                current_image = '../Images/'+ image_files
                CurrentImage=cv2.imread(current_image)
                Content = pt.image_to_string(CurrentImage)
                ImageToText=ImageToText+Content.lower()
            matched = 0
            for entity in IdentifierList:
                if entity in ImageToText:
                    matched = matched+1
            print("Matched:::::::::::::::::::::"+str(matched))
            if matched >= num_of_matches:
                FileAnalysis[file]='Valid'
            else:
                FileAnalysis[file]='Invalid'
            for image_files in os.listdir('../Images'):
                current_image = '../Images/'+ image_files
                os.remove(current_image)
        return{'msg':FileAnalysis}
######### OCR using Google Vision API ##########
class CheckFileValidityGVA(Resource):
    @jwt_required
    def post(self):
        data = request.get_json()     # status code
        num_of_matches = data['number_of_matches']
        client = vision.ImageAnnotatorClient()
        with io.open('../Dataset/DeathCertificate1.png', 'rb') as image_file:
            content = image_file.read()
        print("Read File Completed")
        image = vision.types.Image(content=content)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        print('Texts:')
        for text in texts:
            print('\n"{}"'.format(text.description))
        return {'message':'success'}
#################### Configure URLs #########################
api.add_resource(GetToken, '/getToken')
api.add_resource(CheckFileValidityTesseract, '/checkFileTesseract')
api.add_resource(CheckFileValidityGVA,'/checkFileGVA')
#################  Run Flask Server ##########################
if __name__ == '__main__':
    app.run(debug = True)
