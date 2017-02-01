#!flask/bin/python

# Author: Ngo Duy Khanh
# Email: ngokhanhit@gmail.com
# Git repository: https://github.com/ngoduykhanh/flask-file-uploader
# This work based on jQuery-File-Upload which can be found at https://github.com/blueimp/jQuery-File-Upload/

import os
import PIL
from PIL import Image
import simplejson
import traceback
import boto3
import uuid
import imghdr

from flask import Flask, request, Response, make_response, render_template, redirect, url_for, send_from_directory
from flask_bootstrap import Bootstrap
from werkzeug import secure_filename

from lib.upload_file import uploadfile
from lib.s3upload_file import s3uploadfile


app = Flask(__name__)
app.config['SECRET_KEY'] = 'hard to guess string'
app.config['BUCKET_NAME'] = 'flaskdemo'.format(uuid.uuid4())
app.config['THUMBNAIL_FOLDER'] = '/thumbnail/'
#app.config['UPLOAD_FOLDER'] = 'data/'
#app.config['THUMBNAIL_FOLDER'] = 'data/thumbnail/'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024


ALLOWED_EXTENSIONS = set(['txt', 'gif', 'png', 'jpg', 'jpeg', 'bmp', 'rar', 'zip', '7zip', 'doc', 'docx'])
IGNORED_FILES = set(['.gitignore'])

bootstrap = Bootstrap(app)

#S3client object
s3client = boto3.client('s3')
#S3 resource object
s3resource = boto3.resource('s3')
#bucket object
bucket = s3resource.Bucket(app.config["BUCKET_NAME"])


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def gen_file_name(filename):
    """
    If file was exist already, rename it and return a new name
    """

    i = 1
    while os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        name, extension = os.path.splitext(filename)
        filename = '%s_%s%s' % (name, str(i), extension)
        i += 1

    return filename


def create_thumbnail(image):
    try:
        base_width = 80
        with open('filename', 'wb') as data:
        	bucket.download_fileobj(image, data)
		img = Image.open(data)
        w_percent = (base_width / float(img.size[0]))
        h_size = int((float(img.size[1]) * float(w_percent)))
        img = img.resize((base_width, h_size), PIL.Image.ANTIALIAS)
        thumbnailfilename = 'thumbnail/'.join(image)
        s3client.put_object(Bucket=app.config["BUCKET_NAME"], Key=thumbnailfilename, Body=img)

        return True

    except:
        print traceback.format_exc()
        return False


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
                s3client.put_object(Bucket=app.config["BUCKET_NAME"], Key=filename, Body=files)  #Body=b'It is a test') 
                
                # create thumbnail after saving
                if mime_type.startswith('image'):
                    create_thumbnail(filename)
                
                # get file size after saving
                size = files.content_length

                # return json for js call back
                result = s3uploadfile(name=filename, type=mime_type, size=size)
            
            return simplejson.dumps({"files": [result.get_file()]})

    if request.method == 'GET':
        # get all file in ./data directory
        
        file_display = []

        for obj in bucket.objects.all():
        	#print(obj.key)
        	#print "{name}\t{size}\t{modified}".format(
        	#	name = obj.key,
        	#	size = obj.size,
        	#	modified = obj.last_modified
        	#	)        
			name = obj.key        	
			size = obj.size
			file_saved = s3uploadfile(name=name, size=size)
			file_display.append(file_saved.get_file()) 
            
        return simplejson.dumps({"files": file_display})

    return redirect(url_for('index'))


@app.route("/delete/<string:filename>", methods=['DELETE'])
def delete(filename):
	#obj = bucket.Object(filename)
	response = bucket.delete_objects(
		Delete={
			'Objects': [
				{
					'Key' : filename,
				}
			]
		}
	)
	return simplejson.dumps({filename: 'True'})


# serve static files
@app.route("/thumbnail/<string:filename>", methods=['GET'])
def get_thumbnail(filename):
	thumbnailfilename = 'thumbnail/' + filename
	#print "Thumbnail filename is {name}".format(name = thumbnailfilename)
	obj = bucket.Object(thumbnailfilename)
	content = obj.get()	
	response = make_response(content['Body'].read())
	response.headers['Content-Type'] =  'image/jpeg'
	return response


@app.route("/data/<string:filename>", methods=['GET'])
def get_file(filename):
	obj = bucket.Object(filename)
	content = obj.get()	
	response = make_response(content['Body'].read())
	response.headers['Content-Type'] =  'image/jpeg'
	return response


@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)



