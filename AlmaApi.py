import json
import os
import logging
import xml.etree.ElementTree as ET
import time
import sys
from math import *
import requests
from urllib3.util import Retry
from requests.adapters import HTTPAdapter
from datetime import date

__version__ = '0.1.0'
__api_version__ = 'v1'
__apikey__ = os.getenv('ALMA_API_KEY')
__region__ = os.getenv('ALMA_API_REGION')

ENDPOINTS = {
    'US': 'https://api-na.hosted.exlibrisgroup.com',
    'EU': 'https://api-eu.hosted.exlibrisgroup.com',
    'APAC': 'https://api-ap.hosted.exlibrisgroup.com'
}

FORMATS = {
    'json': 'application/json',
    'xml': 'application/xml'
}

RESOURCES = {
    'reminders' : 'bibs/{bib_id}/reminders',
    'get_reminders' : 'bibs/{bib_id}/reminders?type={type}',
}

NS = {'sru': 'http://www.loc.gov/zing/srw/',
        'marc': 'http://www.loc.gov/MARC21/slim',
        'xmlb' : 'http://com/exlibris/urm/general/xmlbeans'
         }

class AlmaRecords(object):
    """A set of function for interact with Alma Apis in area "Records & Inventory"
    """

    def __init__(self, apikey=__apikey__, region=__region__,service='AlmaPy'):
        if apikey is None:
            raise Exception("Please supply an API key")
        if region not in ENDPOINTS:
            msg = 'Invalid Region. Must be one of {}'.format(list(ENDPOINTS))
            raise Exception(msg)
        self.apikey = apikey
        self.endpoint = ENDPOINTS[region]
        self.service = service
        self.logger =  logging.getLogger(__name__)

    @property
    #Construit la requête et met en forme les réponses
    def baseurl(self):
        """Construct base Url for Alma Api
        
        Returns:
            string -- Alma Base URL
        """
        return '{}/almaws/{}/'.format(self.endpoint, __api_version__)

    def fullurl(self, resource, ids={}):
        return self.baseurl + RESOURCES[resource].format(**ids)

    def headers(self, accept='json', content_type=None):
        headers = {
            "User-Agent": "pyalma/{}".format(__version__),
            "Authorization": "apikey {}".format(self.apikey),
            "Accept": FORMATS[accept]
        }
        if content_type is not None:
            headers['Content-Type'] = FORMATS[content_type]
        return headers
    def get_error_message(self, response, accept):
        """Extract error code & error message of an API response
        
        Arguments:
            response {object} -- API REsponse
        
        Returns:
            int -- error code
            str -- error message
        """
        error_code, error_message = '',''
        if accept == 'xml':
            root = ET.fromstring(response.text)
            error_message = root.find(".//xmlb:errorMessage",NS).text if root.find(".//xmlb:errorMessage",NS).text else response.text 
            error_code = root.find(".//xmlb:errorCode",NS).text if root.find(".//xmlb:errorCode",NS).text else '???'
        else :
            content = response.json()
            error_message = content['errorList'][0]['errorMessage']
            errorCode = content['errorList'][0]['errorCode']
        return error_code, error_message
    
    def request(self, httpmethod, resource, ids, params={}, data=None,
                accept='json', content_type=None, nb_tries=0, in_url=None):
        #20190905 retry request 3 time s in case of requests.exceptions.ConnectionError
        session = requests.Session()
        retry = Retry(connect=3, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        response = session.request(
            method=httpmethod,
            headers=self.headers(accept=accept, content_type=content_type),
            url= self.fullurl(resource, ids) if in_url is None else in_url,
            params=params,
            data=data)
        try:
            response.raise_for_status()  
        except requests.exceptions.HTTPError:
            error_code, error_message= self.get_error_message(response,accept)
            self.logger.warning("Alma_Apis :: HTTP Status: {} || Method: {} || URL: {} || Response: {}".format(response.status_code,response.request.method, response.url, response.text))
            return 'Error', "{} -- {}".format(error_code, error_message)
        except requests.exceptions.ConnectionError:
            error_code, error_message= self.get_error_message(response,accept)
            self.logger.warning("Alma_Apis :: Connection Error: {} || Method: {} || URL: {} || Response: {}".format(response.status_code,response.request.method, response.url, response.text))
            return 'Error', "{} -- {}".format(error_code, error_message)
        except requests.exceptions.RequestException:
            error_code, error_message= self.get_error_message(response,accept)
            self.logger.warning("Alma_Apis :: Connection Error: {} || Method: {} || URL: {} || Response: {}".format(response.status_code,response.request.method, response.url, response.text))
            return 'Error', "{} -- {}".format(error_code, error_message)
        return "Success", response

            

    
    def extract_content(self, response):
        ctype = response.headers['Content-Type']
        if 'json' in ctype:
            return response.json()
        else:
            return response.content.decode('utf-8')
    
    
    def check_reminder(self, bib_id, reminder_type, accept='json'):
        """Retourne True si un reminder du même type existe déjà sur la notice

        Args:
            mms_id ([type]): [description]
            accept (str, optional): [description]. Defaults to 'xml'.

        Returns:
            [type]: [description]
        """
        status,response = self.request('GET', 'get_reminders',
                                {   'bib_id' : bib_id,
                                    'type'  : reminder_type
                                },
                                accept=accept)
        if status == 'Error':
            return status, response
        else:
            reminders_list = self.extract_content(response)
            if reminders_list['total_record_count'] > 0 :
                return status,True
            else :
                return status,False       

    def create_reminder(self, bib_id, error_type, msg):
            """Attache une alerte à i=une notice bibliographique

            Args:
                bib_id (string): mmsid
                type (string) : type de l'alerte


            Returns:
                staus: Sucess ou ERROR
                response: Upadtaed Record or Error message
            """
            today = date.today()
            reminder = {
                        "link": "string",
                        "entity": {
                            "link": "string",
                            "entity_type": {
                            "value": "BIB_MMS"
                            },
                            "entity_id": bib_id
                        },
                        "type": {
                            "value": error_type
                        },
                        "status": {
                            "value": "NEW"
                        },
                        "text": msg,
                        "reminder_date": today.strftime("%Y-%m-%d")
            }
            data = json.dumps(reminder)
            status, response = self.request('POST', 'reminders', 
                                    {'bib_id': bib_id},
                                    data=data, content_type='json', accept='json')
            if status == 'Error':
                return status, response
            else:
                return status, self.extract_content(response)
        