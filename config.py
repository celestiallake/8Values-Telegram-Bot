import psycopg2

API_TOKEN = '' # BotFather

WEBHOOK_HOST = '' # Server IP
WEBHOOK_PORT = 8443 # or 80, or 88, or 443
WEBHOOK_LISTEN = '' #Server IP

WEBHOOK_SSL_CERT = './webhook_cert.pem'
WEBHOOK_SSL_PRIV = './webhook_pkey.pem'

WEBHOOK_URL_BASE = "https://%s:%s" % (WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/{}/".format(API_TOKEN)

def init_db():
	return psycopg2.connect(
	database="",
	user="eightvalues_bot",
	password="8values_bot321",
	host="localhost",
	port=5432
	)

