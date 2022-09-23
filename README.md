# QIS Web Scraper
### requirements
```
pip install -r /path/to/requirements.txt
```
### description
This script allows you to read out your grades from [QIS](https://qisserver.htwk-leipzig.de/qisserver/rds?state=user&type=0). Furthermore, it compares the previous grades, looks for changes, and notifies you via email. Perfectly to deploy on your server and call the script regularly. To use email, you either need to provide your own SMTP Server or use the predefined Google mail. To allow access to Gmail, you need to [enable 2FA and create an app-password](https://support.google.com/accounts/answer/185833). 

### parameters you need to configure
```
# Opal credentials
USERNAME = 'user'
PASSWORD = 'password'

# Gmail credentials
EMAIL = 'sender@example.com'
EMAIL_APP_PW = 'password'

RECIPIENT = 'recipient@example.com'

# proxy
USE_PROXY = False
```
