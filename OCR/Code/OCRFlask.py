from flask import Flask, jsonify, request
from flask_restful import Resource, Api
from flask_jwt_extended import JWTManager,create_access_token,jwt_required
import os,random,datetime,fitz,io,sys,requests,string
from PIL import Image
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
        expires = datetime.timedelta(seconds=2700)
        return {'token':create_access_token(identity=str(random.randint(10000,99999)), expires_delta=expires)}
######### OCR using Google Vision API ##########
class PerformOCRGVA(Resource):
    @jwt_required
    def post(self):
        ################ Get File Name and Minimum Matches From Request ###############
        data = request.get_json()
        file_url = data['file_url']
        ####################### Set Identifier Keywords ###############################
        IdentifierList=['surname','given names','place of death','date of death','occupation & sex','age & date of birth','usual address','place of birth']
        ############## Check If PDF and Image Directory Exists or not ################
        DownloadDirectory="../Downloads/"
        if not(os.path.exists(DownloadDirectory)):
            os.mkdir(DownloadDirectory)
        ExtractedImageDirectory="../Images/"
        if not(os.path.exists(ExtractedImageDirectory)):
            os.mkdir(ExtractedImageDirectory)
        ################### Download File #########################
        letters = string.ascii_lowercase
        if file_url.endswith('.pdf'):
            FileName="File_"+str(random.randint(100000, 999999))+''.join(random.choice(letters) for i in range(5))+".pdf"
        elif file_url.endswith('.jpg'):
            FileName="File_"+str(random.randint(100000, 999999))+''.join(random.choice(letters) for i in range(5))+".jpg"
        elif file_url.endswith('.jpeg'):
            FileName="File_"+str(random.randint(100000, 999999))+''.join(random.choice(letters) for i in range(5))+".jpeg"
        elif file_url.endswith('.png'):
            FileName="File_"+str(random.randint(100000, 999999))+''.join(random.choice(letters) for i in range(5))+".png"
        else:
            return{'msg':'Error','description':'Invalid file. Only pdf/jpg/jpeg/png files are supported.'}
        FilePath=DownloadDirectory+FileName
        try:
            response=requests.get(str(file_url))
        except:
            return{'msg':'Error','description':'Unable to download file. Please check the file url again.'}
        try:
            with open(FilePath,'wb') as f:
                f.write(response.content)
        except:
            return{'msg':'Error','description':'Unable to save downloaded file.'}
        ################ Read Each File and Change to jpeg format ####################
        current_file=FilePath
        ImageName="Image_"+str(random.randint(100000, 999999))+''.join(random.choice(letters) for i in range(5))+".jpeg"
        ImagePath=ExtractedImageDirectory+ImageName
        #image_file=ImagePath
        if current_file.endswith('.pdf'):
            try:
                doc = fitz.open(current_file)
            except:
                os.remove(FilePath)
                return{'msg':'Error','description':'Unable to open downloaded file.'}
            list_of_images = doc.getPageImageList(0)[0]
            if len(list_of_images)==0:
                os.remove(FilePath)
                return{'msg':'Error','description':'No images found in the pdf file.'}
            xref = list_of_images[0]
            pix = fitz.Pixmap(doc, xref)
            if pix.n < 5:
                try:
                    pix.writePNG(ImagePath)
                    os.remove(current_file)
                except:
                    os.remove(current_file)
                    return{'msg':'Error','description':'Unable to extract image from pdf file.'}
            else:
                pix1 = fitz.Pixmap(fitz.csRGB, pix)
                try:
                    pix1.writePNG(ImagePath)
                    os.remove(current_file)
                except:
                    os.remove(current_file)
                    return{'msg':'Error','description':'Unable to extract image from pdf file.'}
                pix1 = None
            pix = None
        else:
            try:
                im = Image.open(current_file)
            except:
                os.remove(FilePath)
                return{'msg':'Error','description':'Unable to open downloaded file.'}
            try:
                im.save(ImagePath)
                os.remove(current_file)
            except:
                os.remove(current_file)
                return{'msg':'Error','description':'Unable to save image file.'}
        ################### Check File Size #######################
        while os.stat(ImagePath).st_size > 9437184:
            im = Image.open(ImagePath)
            im.save(ImagePath,optimize=True,quality=80)
        ################# Call Google vision API ##################
        with io.open(ImagePath, 'rb') as gen_image_file:
            content = gen_image_file.read()
        try:
            client = vision.ImageAnnotatorClient()
            image = vision.types.Image(content=content)
            response = client.text_detection(image=image)
            os.remove(ImagePath)
        except:
            os.remove(ImagePath)
            return {'msg':'Error','description':'Unable to invoke Google vision api.'}
        ############ Create Dict for Vision API response ###########
        DictResponse=MessageToDict(response)
        ########## Check For Document Orientation ##################
        WholeContentVertices=DictResponse['textAnnotations'][0]['boundingPoly']['vertices']
        start_x=WholeContentVertices[0]['x']
        end_x=WholeContentVertices[1]['x']
        x_duration=int(end_x)-int(start_x)
        start_y=WholeContentVertices[0]['y']
        end_y=WholeContentVertices[2]['y']
        y_duration=int(end_y)-int(start_y)
        ratio=y_duration/x_duration
        if (ratio < 1.4) or (ratio > 1.6) :
            return {'msg':'Error','description':'Image orientation is invalid.'}
        ########## Check If all words found or not ##################
        WholeContentDescription=DictResponse['textAnnotations'][0]['description'].lower()
        count=0
        for entity in IdentifierList:
            if entity in WholeContentDescription:
                count=count+1
        IsValid=False
        if count==len(IdentifierList):
            IsValid=True
        if not(IsValid):
            return {'msg':'Error','description':'Google Vision API only found {} out of 8 mandatory keywords.'.format(count)}
        else:
            ############## Create List for vertex and word #############
            WordsAndCoordinates=DictResponse['textAnnotations'][1:]
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
            lly_ll=lly_surname-15
            lly_ul=lly_surname+15
            SurnameList=list(WordsAndCoordinatesDFCopy[(WordsAndCoordinatesDFCopy['Word']!='Surname') & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
            SurnameList
            Surname=" "
            Surname=Surname.join(SurnameList)
            ################### Get Given Name ##############################
            lly_Given=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['Given'])]['lly'].values[0]
            lly_ll=lly_Given-15
            lly_ul=lly_Given+15
            GivenNameList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Given','Names'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
            GivenName=" "
            GivenName=GivenName.join(GivenNameList)
            ################## Get Place Of Death ###########################
            lly_place_of_death=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['Place'])].head(1)['lly'].values[0]
            lly_ll=lly_place_of_death-15
            lly_ul=lly_place_of_death+15
            PlaceOfDeathList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Place','of','death'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
            PlaceOfDeath=" "
            PlaceOfDeath=PlaceOfDeath.join(PlaceOfDeathList)
            #################### Get Date Of Death #######################
            lly_date_of_death=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['Date'])].head(1)['lly'].values[0]
            lly_ll=lly_date_of_death-15
            lly_ul=lly_date_of_death+15
            DateOfDeathList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Date','of','death'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
            DateOfDeath=" "
            DateOfDeath=DateOfDeath.join(DateOfDeathList)
            ################# Get Occupation And Sex #####################
            lly_occupation_and_sex=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['Occupation'])].head(1)['lly'].values[0]
            lly_ll=lly_occupation_and_sex-15
            lly_ul=lly_occupation_and_sex+15
            OccupationAndSexList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Occupation','&','Sex'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
            OccupationAndSex=" "
            OccupationAndSex=OccupationAndSex.join(OccupationAndSexList).split(' ')
            if 'Male' in OccupationAndSex:
                Sex="Male"
                OccupationAndSexList.remove("Male")
            elif "Female" in OccupationAndSex:
                Sex="Female"
                OccupationAndSexList.remove("Female")
            else:
                return {'msg':'Error','description':'Google Vision API failed to find the world Male or Female in sex.'}
            Occupation=" "
            Occupation=Occupation.join(OccupationAndSexList)
            ################# Get Age And Date Of Birth ###################
            lly_age_and_dob=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['Age'])].head(1)['lly'].values[0]
            lly_ll=lly_age_and_dob-15
            lly_ul=lly_age_and_dob+15
            AgeAndDOBList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Age','&','Date','of','Birth'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
            AgeAndDOB=" "
            AgeAndDOB=AgeAndDOB.join(AgeAndDOBList)
            if 'years' not in AgeAndDOB:
                return {'msg':'Error','description':'Google Vision API failed to find the world years in Age & DOB.'}
            AgeAndDOBSeg=AgeAndDOB.split('years ')
            Age=str(AgeAndDOBSeg[0])+"years"
            DOB=AgeAndDOBSeg[1]
            ############### Get Usual Address ##############################
            lly_usual_address=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['address'])].head(1)['lly'].values[0]
            lly_ll=lly_usual_address-15
            lly_ul=lly_usual_address+15
            UsualAddressList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Usual','address'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
            UsualAddress=" "
            UsualAddress=UsualAddress.join(UsualAddressList)
            if len(UsualAddress)==0:
                print("Inside check "+str(len(UsualAddress)))
                lly_ll=lly_usual_address-40
                lly_ul=lly_usual_address+40
                UsualAddressList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Usual','address'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
                UsualAddress=UsualAddress.join(UsualAddressList)
            ################## Get Place Of Birth ############################
            lly_place_of_birth=WordsAndCoordinatesDFCopy[WordsAndCoordinatesDFCopy['Word'].isin(['birth'])].head(1)['lly'].values[0]
            lly_ll=lly_place_of_birth-15
            lly_ul=lly_place_of_birth+15
            PlaceOfBirthList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Place','of','birth'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
            PlaceOfBirth=" "
            PlaceOfBirth=PlaceOfBirth.join(PlaceOfBirthList)
            if len(PlaceOfBirth)==0:
                lly_ll=lly_place_of_birth-40
                lly_ul=lly_place_of_birth+40
                PlaceOfBirthList=list(WordsAndCoordinatesDFCopy[(~WordsAndCoordinatesDFCopy['Word'].isin(['Place','of','birth'])) & (WordsAndCoordinatesDFCopy['lly'].between(lly_ll,lly_ul))][['Word']].sort_index()['Word'])
                PlaceOfBirth=PlaceOfBirth.join(PlaceOfBirthList)
            return {'message':'success','Surname':Surname,'GivenName':GivenName,'PlaceOfDeath':PlaceOfDeath,'DateOfDeath':DateOfDeath,'Occupation':Occupation,'Sex':Sex,'Age':Age,'DateOfBirth':DOB,'UsualAddress':UsualAddress,'PlaceOfBirth':PlaceOfBirth}
#################### Configure URLs #########################
api.add_resource(GetToken, '/getToken')
api.add_resource(PerformOCRGVA,'/checkFileGVA')
#################  Run Flask Server ##########################
if __name__ == '__main__':
    app.run(debug = True)
