import os
import re
import json
import itertools
import socket
import sys
from bs4 import BeautifulSoup
import requests
from urllib.parse import urlparse, parse_qs
import smtplib
import logging
from logging import handlers
import time

# Opal credentials
USERNAME = 'user'
PASSWORD = 'password'

# Gmail credentials: Sending Emails requires you to create an app password: https://support.google.com/accounts/answer/185833
EMAIL = 'sender@example.com'
EMAIL_APP_PW = 'password'

RECIPIENT = 'recipient@example.com'

# proxy
USE_PROXY = False




# working paths
work_path = os.path.dirname(os.path.realpath(__file__))
storage_path = os.path.join(work_path, "qis-storage")
grades_path = os.path.join(storage_path, "grades.json")
params_path = os.path.join(storage_path, "params.json")
log_path = os.path.join(storage_path, "logs")

# proxy settings
if USE_PROXY:
    os.environ['HTTP_PROXY'] = os.environ['http_proxy'] = ''
    os.environ['HTTPS_PROXY'] = os.environ['https_proxy'] = ''
    os.environ['NO_PROXY'] = os.environ['no_proxy'] = ''

def log_setup():
    create(log_path, "dir")
    handler = handlers.TimedRotatingFileHandler(filename=f'{log_path}/main.log', when='midnight', backupCount=14, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-8s %(message)s', datefmt='%d.%m.%Y %H:%M:%S'))
    logger = logging.getLogger()
    logger.addHandler(handler)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logger.setLevel(logging.DEBUG)

def gethref(response):
    href = []
    soup = BeautifulSoup(response, 'html.parser')
    for link in soup.find_all('a'):
        href.append(link.get('href'))
    return href

def searchforhref(response, searchparam): #only returns the first result
    for href in gethref(response):
        try:
            parsed_url = urlparse(href)
            return parse_qs(parsed_url.query)[searchparam][0]
        except KeyError:
            pass

def send_email(user, pwd, recipient, subject, body):
    FROM = user
    TO = recipient if isinstance(recipient, list) else [recipient]
    SUBJECT = subject
    TEXT = body

    # Prepare actual message
    message = """From: %s\nTo: %s\nSubject: %s\n\n%s
    """ % (FROM, ", ".join(TO), SUBJECT, TEXT)
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(user, pwd)
        server.sendmail(FROM, TO, message)
        server.close()
        logger.info('successfully sent the mail')
    except (smtplib.SMTPException, socket.error) as e:
        logger.error(f"failed to send mail: {e}")

# create function for dirs and paths
def create(path, type):
    if not os.path.exists(path):
        if type == "dir":
            os.mkdir(path)
            return True
        elif type == "file" :
            with open(path, 'w'): return True
        else:
            raise ValueError
    else:
        return False

# create the working folder
create(storage_path, "dir")

# logging settings
start_time = time.time()
log_setup()
logger = logging.getLogger(__name__)

# Start the session
session = requests.Session()

# Create the payload
data = {'username': USERNAME, 'password': PASSWORD, 'submit':'Anmelden'}
BASEURL = "https://qisserver.htwk-leipzig.de/qisserver/rds"

# Start the session
session = requests.Session()

# post the payload to the site to log in and extract the asi parameter for all future requests
r = session.post(f'{BASEURL}?state=user&type=1&category=auth.login&startpage=portal.vm&topitem=functions&breadCrumbSource=portal', data=data)
logger.debug(f"login process took {r.elapsed.total_seconds()} seconds")
asi = searchforhref(r.text, "asi")

# save params to file to make future requests more efficient 
if create(params_path, "file"):
    logger.debug("updating the parameters")
    with open(params_path, 'w', encoding='utf-8') as f:
        # Get nodeID for diploma and matriculation year selector
        r = session.get(f'{BASEURL}?state=notenspiegelStudent&next=tree.vm&nextdir=qispos/notenspiegel/student&menuid=notenspiegelStudent&asi={asi}')
        logger.debug(f"calling overview took {r.elapsed.total_seconds()} seconds")
        nodeID = searchforhref(r.text, "nodeID")
        logger.debug(f"nodeID is now '{nodeID}'")
        json.dump({"nodeID": nodeID}, f, ensure_ascii=False, indent=4)
else:
    logger.debug("found existing parameters")
    with open(params_path, 'r', encoding='utf-8') as f:
        try: 
            nodeID = json.load(f)["nodeID"]
        except (json.decoder.JSONDecodeError, KeyError) as e:
            f.close()
            logger.error("unexpected config file, removing config file. Please restart program")
            os.remove(params_path)
            sys.exit()

# navigate to the page, containing the grades
r = session.get(f'{BASEURL}?state=notenspiegelStudent&next=list.vm&nextdir=qispos/notenspiegel/student&menuid=notenspiegelStudent&createInfos=Y&struct=auswahlBaum&expand=0&asi={asi}&nodeID={nodeID}')
logger.debug(f"calling grade page took {r.elapsed.total_seconds()} seconds")
soup = BeautifulSoup(r.text, 'html.parser')
exams = soup.find_all('tr', class_= ['MP', 'PL']) # Teilleistung oder Modulprüfung
parsedExams = {}
for exam in exams:
    examname = exam.find('span', class_='examName').getText()
    publishDate = re.search(r'\d{2}\.\d{2}\.\d{4}', exam.find('span', class_='comment').get_text())
    grade = re.search("[^\t\n\r\s]+", exam.find_all('td' , class_= 'grade')[-1].text)[0] # select last element because class is used muliple times. remove control characters
    parsedExams[examname if examname not in parsedExams else f"{examname} - {publishDate[0]}"] = grade

# read saved grades and compare
if not create(grades_path, "file"):
    with open(grades_path, 'r', encoding='utf-8') as f:
        grades = json.load(f)
    # get completely new grades
    diff = list(itertools.filterfalse(lambda x: x in grades, parsedExams)) + list(itertools.filterfalse(lambda x: x in parsedExams, grades))
    # search for different values
    for module in (list(grades.keys()) + list(set(parsedExams.keys()) - set(grades.keys()))):
        if module in grades and module in parsedExams and grades[module] != parsedExams[module]:
            diff = list(set(diff + [module])) # makes sure that the module only occurs once
    if(diff):
        logger.debug(f"found difference(s) in saved grades: {diff}")
        message = f"The following grade(s) have changed: \n{diff} \ngo to https://qisserver.htwk-leipzig.de/qisserver/rds?state=user&type=0 to view details. \n"
        if not USE_PROXY:
            send_email(EMAIL, EMAIL_APP_PW, RECIPIENT, "QIS - new grades just have been published", message)
        else: # no SMTP support for http Proxy 
            print(message)
    else:
        logger.debug("no changed grades")
        print("no changed grades") # for commandline purposes 

# save current grades
with open(grades_path, 'w', encoding='utf-8') as f:
    json.dump(parsedExams, f, ensure_ascii=False, indent=4)

logger.debug("finished. total elapsed time: %.2f seconds" % (time.time() - start_time))
