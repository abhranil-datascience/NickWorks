from flask import Flask, jsonify, request
from flask_restful import Resource, Api
from flask_jwt_extended import JWTManager,create_access_token,jwt_required
import os,random,datetime,fitz,cv2,io,sys
from PIL import Image
import pytesseract as pt
from google.cloud import vision
from google.cloud.vision import types
from google.protobuf.json_format import MessageToDict
import pandas as pd
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
        expires = datetime.timedelta(seconds=300)
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
        ################ Get File Name From Request ###############
        data = request.get_json()
        FilePath = data['FilePath']
        current_file="../Dataset/"+FilePath
        ############### Check If a pdf/other file ################
        count=1
        if FilePath.endswith('.pdf'):
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
        ##################   Grab Image ###########################
        current_image = '../Images/Image1.png'
        ################# Call Google vision API ##################
        with io.open(current_image, 'rb') as image_file:
            content = image_file.read()
        try:
            client = vision.ImageAnnotatorClient()
            image = vision.types.Image(content=content)
            response = client.text_detection(image=image)
        except:
            return {'error':'unable to invoke Google vision api.'}
        ############ Create Dict for Vision API response ###########
        DictResponse=MessageToDict(response)
        WordsAndCoordinates=DictResponse['textAnnotations'][1:]
        ############## Create List for vertex and word #############
        word_list=[]
        llx_list=[]
        lly_list=[]
        lrx_list=[]
        lry_list=[]
        urx_list=[]
        ury_list=[]
        ulx_list=[]
        uly_list=[]
        for i in range(0,len(WordsAndCoordinates)):
            word_list.append(WordsAndCoordinates[i]['description'])
            llx_list.append(WordsAndCoordinates[i]['boundingPoly']['vertices'][0]['x'])
            lly_list.append(WordsAndCoordinates[i]['boundingPoly']['vertices'][0]['y'])
            lrx_list.append(WordsAndCoordinates[i]['boundingPoly']['vertices'][1]['x'])
            lry_list.append(WordsAndCoordinates[i]['boundingPoly']['vertices'][1]['y'])
            urx_list.append(WordsAndCoordinates[i]['boundingPoly']['vertices'][2]['x'])
            ury_list.append(WordsAndCoordinates[i]['boundingPoly']['vertices'][2]['y'])
            ulx_list.append(WordsAndCoordinates[i]['boundingPoly']['vertices'][3]['x'])
            uly_list.append(WordsAndCoordinates[i]['boundingPoly']['vertices'][3]['y'])
        ##################### Create Dictionary for the lists #####################
        WordsAndCoordinatesDict={"Word":word_list,'llx':llx_list,'lly':lly_list,'lrx':lrx_list,'lry':lry_list,'urx':urx_list,'ury':ury_list,'ulx':ulx_list,'uly':uly_list}
        ####################### Create Dataframe ######################
        WordsAndCoordinatesDF = pd.DataFrame.from_dict(WordsAndCoordinatesDict)
        ###################### Get only region of interest i.e. from Surname till Place Of Birth ###################
        lly_ll=WordsAndCoordinatesDF[WordsAndCoordinatesDF['Word'].isin(["Surname"])].head(1)['lly'].values[0]-40
        lly_ul=WordsAndCoordinatesDF[WordsAndCoordinatesDF['Word'].isin(["birth"])]['lly'].values[0]+40
        WordsAndCoordinatesDFCopy=WordsAndCoordinatesDF[WordsAndCoordinatesDF['lly'].between(lly_ll,lly_ul)]
        WordsAndCoordinatesDFCopy=WordsAndCoordinatesDFCopy.sort_values(by=['lly'])
        ##################### Get Surname ############################
        lly_surname=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['Surname'])]['lly'].values[0]
        lly_ll=lly_surname-20
        lly_ul=lly_surname+20
        SurnameList=list(WordsAndCoordinatesDFCopy[(WordsAndCoordinatesDFCopy['Word']!='Surname') & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
        SurnameList
        Surname=" "
        Surname=Surname.join(SurnameList)
        ################### Get Given Name ##############################
        lly_Given=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['Given'])]['lly'].values[0]
        lly_ll=lly_Given-20
        lly_ul=lly_Given+20
        GivenNameList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Given','Names'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
        GivenName=" "
        GivenName=GivenName.join(GivenNameList)
        ################## Get Place Of Death ###########################
        lly_place_of_death=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['Place'])].head(1)['lly'].values[0]
        lly_ll=lly_place_of_death-20
        lly_ul=lly_place_of_death+20
        PlaceOfDeathList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Place','of','death'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
        PlaceOfDeath=" "
        PlaceOfDeath=PlaceOfDeath.join(PlaceOfDeathList)
        #################### Get Date Of Death #######################
        lly_date_of_death=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['Date'])].head(1)['lly'].values[0]
        lly_ll=lly_date_of_death-20
        lly_ul=lly_date_of_death+20
        DateOfDeathList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Date','of','death'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
        DateOfDeath=" "
        DateOfDeath=DateOfDeath.join(DateOfDeathList)
        ################# Get Occupation And Sex #####################
        lly_occupation_and_sex=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['Occupation'])].head(1)['lly'].values[0]
        lly_ll=lly_occupation_and_sex-20
        lly_ul=lly_occupation_and_sex+20
        OccupationAndSexList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Occupation','&','Sex'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
        OccupationAndSex=" "
        OccupationAndSex=OccupationAndSex.join(OccupationAndSexList)
        ################# Get Age And Date Of Birth ###################
        lly_age_and_dob=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['Age'])].head(1)['lly'].values[0]
        lly_ll=lly_age_and_dob-20
        lly_ul=lly_age_and_dob+20
        AgeAndDOBList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Age','&','Date','of','Birth'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
        AgeAndDOB=" "
        AgeAndDOB=AgeAndDOB.join(AgeAndDOBList)
        ############### Get Usual Address ##############################
        lly_usual_address=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['address'])].head(1)['lly'].values[0]
        lly_ll=lly_usual_address-20
        lly_ul=lly_usual_address+20
        UsualAddressList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Usual','address'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
        UsualAddress=" "
        UsualAddress=UsualAddress.join(UsualAddressList)
        ################## Get Place Of Birth ############################
        lly_place_of_birth=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['birth'])].head(1)['lly'].values[0]
        lly_ll=lly_place_of_birth-20
        lly_ul=lly_place_of_birth+20
        PlaceOfBirthList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Place','of','birth'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
        PlaceOfBirth=" "
        PlaceOfBirth=PlaceOfBirth.join(PlaceOfBirthList)
        for image_files in os.listdir('../Images'):
            current_image = '../Images/'+ image_files
            os.remove(current_image)
        return {'message':'success','Surname':Surname,'GivenName':GivenName,'PlaceOfDeath':PlaceOfDeath,'DateOfDeath':DateOfDeath,'OccupationAndSex':OccupationAndSex,'AgeAndDOB':AgeAndDOB,'UsualAddress':UsualAddress,'PlaceOfBirth':PlaceOfBirth}
#################### Configure URLs #########################
api.add_resource(GetToken, '/getToken')
api.add_resource(CheckFileValidityTesseract, '/checkFileTesseract')
api.add_resource(CheckFileValidityGVA,'/checkFileGVA')
#################  Run Flask Server ##########################
if __name__ == '__main__':
    app.run(debug = True)
