#!/usr/bin/env python

import os
from rq import Queue
from redis import Redis
import logging
import base64
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
import requests
from datetime import date, datetime, timedelta


logging.basicConfig(level=logging.INFO,
                    format='(%(threadName)-10s) %(message)s',
                    )

## VARIABLES AND PARAMETERS START  ##
redis_host = os.getenv('MESSAGE_QUEUE_SERVICE_HOST','192.168.99.100')
redis_port = int(os.getenv('MESSAGE_QUEUE_SERVICE_PORT', 6379))
mongodb_host = os.getenv('DATABASE_SERVICE_HOST','192.168.99.100')
mongodb_port = int(os.getenv('DATABASE_SERVICE_PORT', 27017))
start_date_string = os.getenv('START_DATE','2015-09-16')
start_date = datetime.strptime(start_date_string,'%Y-%m-%d').date()
client = MongoClient(mongodb_host,mongodb_port)
db = client.extractor
BASE_URL= "https://www.bnz.co.nz"
ENDPOINT = BASE_URL + "/ib/api/accounts/"
auth = os.getenv('SECRET_BNZ_TOKEN')
verify=True
token_queue = Queue('token-queue',connection=Redis(host=redis_host,port=redis_port))
transaction_queue = Queue('transaction-queue',connection=Redis(host=redis_host,port=redis_port))
headers = {'Host':'www.bnz.co.nz',
           'Connection':'keep-alive',
           'Pragma':'no-cache',
           'Cache-Control':'no-cache',
           'Accept':'application/json, text/javascript, */*; q=0.01','X-API-Client-ID':'YouMoney',
           'X-Requested-With':'XMLHttpRequest',
           'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_3) AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/56.0.2924.87 Safari/537.36',
            'Referer':'https://www.bnz.co.nz/client/',
            'Accept-Encoding':'gzip, deflate, sdch, br',
            'Accept-Language':'en-US,en;q=0.8,es;q=0.6,it-IT;q=0.4,it;q=0.2',
            'Cookie':auth}

## VARIABLES AND PARAMETERS END  ##

logging.debug("Worker: Redis info: " + redis_host)


def get_accounts():
    logging.info('Connecting to BNZ to get a list of Bank Accounts')
    logging.info('Connected')
    get_accounts_response = requests.get(ENDPOINT, headers=headers, verify=verify, allow_redirects=False)
    if get_accounts_response.status_code != 200:
        logging.error("Response is not OK. Maybe your token has expired. Finishing script")
        from time import sleep
        sleep(5)
        exit(-1)
    accounts_info = get_accounts_response.json()
    for account in accounts_info['accountList']:
        account_data = {"_id": account['id'], "account_name": account['nickname'], "endpoint": ENDPOINT + account['id']}
        logging.info('Found an account: ' + account_data.get('account_name'))
        __add_account(account_data)

def save_token(token):
    from kubernetes import client, config

    # Configs can be set in Configuration class directly or using helper utility
    config.load_kube_config()
    api_instance = client.CoreV1Api()
    sec = client.V1Secret()
    sec.metadata = client.V1ObjectMeta(name="bnz")
    sec.type = "Opaque"
    sec.data = {"token":token}
    api_instance.replace_namespaced_secret(name="bnz",namespace="default", body=sec)
    logging.debug('Token saved')


def __add_account(account):
    try:
        result = db.accounts.insert_one(account)
        logging.info("Added new account in db " + str(result.inserted_id))
    except DuplicateKeyError:
        logging.debug('Account already exists. Skipping....')
    transaction_queue.enqueue(prepare_get_transaction_queue,account)


def prepare_get_transaction_queue(account): #account
    end_date = str(date.today() - timedelta(1)) # Yesterday
    transactions = db.transactions

    transactions_list = __get_account_transactions(account, start_date,end_date)
    logging.info(str(len(transactions_list)) + ' transactions were returned from BNZ')
    for trans in transactions_list:
        try:
            trans['_id'] = trans['transactionIdentifier']
            transactions.insert_one(trans)
            logging.info('Added new transaction ' +  trans['_id'] + ' in database')
        except DuplicateKeyError:
            logging.error('Transaction ' +  trans['_id'] + ' already in the database. Skipping')


def prepare_get_transaction_queue2(account): #account
    import pdb; pdb.set_trace()
    end_date = str(date.today() - timedelta(1)) # Yesterday
    accounts = db.accounts
    transactions = db.transactions
    account_in_database = accounts.find_one(account['_id'])
    last_transaction_date = account_in_database.get('lastDownloadedDate')

    # if last_transaction_date:
    #     #compare dates
    #     logging.debug('Download from ')
    #     logging.info('Account:'+ account['account_name'] +' download from: lastTransactionDate '+ str(last_transaction_date) + ' to: ' + str(end_date))
    #     list = __get_account_transactions(account, last_transaction_date,end_date)
    # else:
    logging.debug('First Time running this')
    logging.info('Account:'+ account['account_name'] +' download from: StartDate:  '+ str(start_date) + ' to: ' + str(end_date))
    list = __get_account_transactions(account, start_date,end_date)
    for trans in list:
        try:
            trans['_id'] = trans['transactionIdentifier']
            transactions_in_accounts = account_in_database.get('transactions',None)
            if transactions_in_accounts is None:
                account_in_database['transactions'] = []
            account_in_database['transactions'].append(trans['_id'])
            #  Gets the date from the account and compare with the one from the transaction. If the transaction one is newer, change it
            # If empty, add the one from the transaction.
            date_in_account=account_in_database.get('lastDownloadedDate',None)
            trans_date=trans.get('date',None)
            if date_in_account is not None:
                if trans_date > date_in_account: # trans date is sooner
                    account_in_database['lastDownloadedDate'] = trans_date
                    logging.info('Date in transaction is newer. Updating lastDownloadedDate field ')
                    accounts.find_one_and_replace(account,account_in_database)
                else:
                    logging.info('Last downloaded date is newer than transaction date')
                    accounts.find_one_and_replace(account,account_in_database) # Saving just the transaction id into the account
            else:
                logging.info('First transaction being saved')
                account_in_database['lastDownloadedDate'] = trans_date
                accounts.find_one_and_replace(account, account_in_database)
            transactions.insert_one(trans)
            logging.info('Added new transaction' +  trans['_id'] + ' in database')

        except DuplicateKeyError:
            logging.error('Transaction' +  trans['_id'] + ' already in the database. Skipping')


def __get_account_transactions(account, sdate, edate):
    get_transaction_url = account['endpoint'] + '/transactions?startDate=' + str(sdate) + '&endDate=' + str(edate)
    transactions_request = requests.get(get_transaction_url, headers=headers, verify=verify)
    if transactions_request.status_code == 200:
        transactions = transactions_request.json().get('transactions',None)
        return transactions
    else:
        logging.error("Response is not OK. Maybe your token has expired. Finishing script")
        from time import sleep
        sleep(5)
        exit(-1)
