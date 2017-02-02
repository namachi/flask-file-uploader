#!flask/bin/python

# Author: Shiva Thirumazhusai
# Email: shiva@nasotech.com
# Git repository: https://github.com/namachi/flask-file-uploader
# This is a fork from https://github.com/namachi/flask-file-uploader
# This work based on jQuery-File-Upload which can be found at https://github.com/blueimp/jQuery-File-Upload/

import os
import PIL
from PIL import Image
import cStringIO as StringIO
import simplejson
import traceback
import boto3
import uuid
import imghdr
import io
import binascii

from flask import Flask, request, Response, make_response, render_template, redirect, url_for, send_from_directory
from flask_bootstrap import Bootstrap
from werkzeug import secure_filename

#file for converting the meta data to readable text format
from lib.s3upload_file import s3uploadfile


#Base configuration. AWS Bucket name, Temp folder for caching(Thumbnail), and file size check
app = Flask(__name__)
app.config['BUCKET_NAME'] = 'flaskdemo'.format(uuid.uuid4())
app.config['THUMBNAIL_FOLDER'] = 'thumbnail/'
app.config['TEMP_FOLDER'] = '/tmp/flaskdemo/'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

#Allowed mime types based on the extension. 
ALLOWED_EXTENSIONS = set(['txt', 'csv', 'gif', 'png', 'jpg', 'jpeg', 'bmp', 'rar', 'zip', '7zip', 'doc', 'docx'])
IGNORED_FILES = set(['.gitignore'])

bootstrap = Bootstrap(app)

#S3client object connecting to AWS services
s3client = boto3.client('s3')
#S3 resource object connecting to AWS services
s3resource = boto3.resource('s3')
#bucket object linked to configured AWS Bucket Name
bucket = s3resource.Bucket(app.config["BUCKET_NAME"])


#Checking the allowed extensions
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


#Creating alternate filenames
def gen_file_name(filename):
    """
    If file was exist already, rename it and return a new name
    """

    i = 1
    while os.path.exists(os.path.join(app.config['TEMP_FOLDER'], filename)):
        name, extension = os.path.splitext(filename)
        filename = '%s_%s%s' % (name, str(i), extension)
        i += 1

    return filename

#Creating Thumbnail image and upload it to the thumbnail folder
def create_thumbnail(imagefilename):
    try:
    	#Download the file to local cache
        base_width = 80
        #print 'Image filename is <<' + imagefilename + '>>'
        #tmpfilename = gen_file_name(imagefilename)
        tmp_file_path = app.config['TEMP_FOLDER'] + imagefilename
        #print 'Thumbnail Image filename path is <<' + tmp_file_path + '>>'        
        s3client.download_file(app.config['BUCKET_NAME'], imagefilename, tmp_file_path)
        
        #Resize the image to thumbnail image size
        img = Image.open(tmp_file_path)
        w_percent = (base_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        img = img.resize((base_width, h_size), PIL.Image.ANTIALIAS)
        img.save(tmp_file_path)
                
        #Upload the thumbnail to the thumbnailfolder in the bucket
        thumbnailfilename = app.config['THUMBNAIL_FOLDER'] + imagefilename
        #print 'Thumbnail filename create is <<' + thumbnailfilename + '>>'
        s3client.upload_file(tmp_file_path, app.config['BUCKET_NAME'], thumbnailfilename)
        #s3client.put_object(Bucket=app.config['BUCKET_NAME'], Key=thumbnailfilename, Body=img)
        
        return True

    except:
        print traceback.format_exc()
        return False

#Upload the files to the site
@app.route("/upload", methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        files = request.files['file']

        if files:
            filename = secure_filename(files.filename)
            #filename = gen_file_name(filename)
            mime_type = files.content_type

            if not allowed_file(files.filename):
                result = s3uploadfile(name=filename, type=mime_type, size=0, not_allowed_msg="File type not allowed")

            else:
                # save file to disk
                s3client.put_object(Bucket=app.config['BUCKET_NAME'], Key=filename, Body=files) 
                
                # create thumbnail after saving
                if mime_type.startswith('image'):
                	#print 'It is a image file. Create Thumbnail ' + filename                
                	create_thumbnail(filename)

                
                # get file size after saving
                size = files.content_length
                print 'File size is <<' + str(size)  + '>>'

                # return json for js call back
                result = s3uploadfile(name=filename, type=mime_type, size=size)
            
            return simplejson.dumps({"files": [result.get_file()]})

    if request.method == 'GET':
        # get all file in ./data directory
        
        file_display = []

        for obj in bucket.objects.all():  
			name = obj.key
			#size = obj.size
			size = obj.content_length
			print 'Object Key <<' + name + '>> size is <<' + str(size)  + '>>'
			file_saved = s3uploadfile(name=name, size=size)
			file_display.append(file_saved.get_file()) 
            
        return simplejson.dumps({"files": file_display})

    return redirect(url_for('index'))

#Delete a file
@app.route("/delete/<string:filename>", methods=['DELETE'])
def delete(filename):
	#delete the main file
	response = bucket.delete_objects(
		Delete={
			'Objects': [
				{
					'Key' : filename,
				}
			]
		}
	)
	#delete thumbnail file
	thumbnailfilename = app.config['THUMBNAIL_FOLDER'] + filename	
	thumbnailresponse = bucket.delete_objects(
		Delete={
			'Objects': [
				{
					'Key' : thumbnailfilename,
				}
			]
		}
	)
	
	return simplejson.dumps({filename: 'True'})


#Serve static files including thumbnail files.
@app.route("/thumbnail/<string:filename>", methods=['GET'])
def get_thumbnail(filename):
	#thumbnailfilename = 'thumbnail/' + filename
	thumbnailfilename = app.config['THUMBNAIL_FOLDER'] + filename
	print 'Thumbnail image name is ' + thumbnailfilename
	obj = bucket.Object(thumbnailfilename)
	content = obj.get()	
	response = make_response(content['Body'].read())
	response.headers['Content-Type'] =  'image/jpeg'
	return response

#Serve the data file
@app.route("/data/<string:filename>", methods=['GET'])
def get_file(filename):
	print 'Filename name is ' + filename
	obj = bucket.Object(filename)
	content = obj.get()	
	response = make_response(content['Body'].read())
	response.headers['Content-Type'] =  'image/jpeg'
	return response

#Serve Root 
@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)



