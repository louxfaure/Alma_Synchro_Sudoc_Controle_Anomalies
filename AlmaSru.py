import os
# external imports
import requests
import xml.etree.ElementTree as ET
import logging
import urllib.parse
# internal import




ns = {'sru': 'http://www.loc.gov/zing/srw/',
        'marc': 'http://www.loc.gov/MARC21/slim' }


class AlmaSru(object):

    def __init__(self, query, index,institution ='network',service='AlmaSru',instance='Prod'):
        self.logger = logging.getLogger(service)
        self.institution = institution
        self.service = service
        self.instance = instance
        self.query = query
        self.index = index
        self.result = self.sru_request()
        if self.status == True :
            nb_result = self.get_nombre_resultats()
            if  nb_result != '1' :
                self.status = False
                self.error_msg = "0 ou plusieus notices pour le même MMSID"
            else :
                self.status = True
                self.error_msg = ""
    @property

    def baseurl(self):
        if self.instance == 'Test' :
            return "https://pudb-{}-psb.alma.exlibrisgroup.com/view/sru/{}?version=1.2&operation=searchRetrieve".format(self.institution.lower(),"33PUDB_"+self.institution.upper())
        else :
            return "https://pudb-{}.alma.exlibrisgroup.com/view/sru/{}?version=1.2&operation=searchRetrieve".format(self.institution.lower(),"33PUDB_"+self.institution.upper())

    def fullurl(self, query, reponseFormat,index,noticesSuppr,complex_query):
        return self.baseurl + '&format=' + reponseFormat + '&query=' + self.searchQuery(query, index, noticesSuppr, complex_query)

    def searchQuery(self, query, index, noticesSuprr, complex_query):
        if complex_query :
            searchQuery = query
        else :
            searchQuery = index
            searchQuery += '='
            searchQuery += query
        if not noticesSuprr:
            searchQuery += '&alma.mms_tagSuppressed=false'
        # return urllib.parse.quote(searchQuery)
        return searchQuery

    def sru_request(self, reponseFormat='marcxml',noticesSuppr=False, complex_query=False):
        url=self.fullurl(self.query,reponseFormat, self.index,noticesSuppr,complex_query)
        self.logger.debug("{} :: alma_sru :: {}".format(self.query,url))
        r = requests.get(url)
        try:
            r.raise_for_status()  
        except requests.exceptions.HTTPError:
            self.status = False
            self.logger.error("{} :: {} :: HTTP Status: {} || Method: {} || URL: {} || Response: {}".format(self.query, 
                                                                                                            self.service ,
                                                                                                            r.status_code,
                                                                                                            r.request.method,
                                                                                                            r.url,
                                                                                                            r.text))
            self.error_msg = "{} :: {} :: HTTP Status: {} || Method: {} || URL: {} || Response: {}".format(self.query, 
                                                                                                            self.service ,
                                                                                                            r.status_code,
                                                                                                            r.request.method,
                                                                                                            r.url,
                                                                                                            r.text)
        else:
            self.status = True
            reponse = r.content.decode('utf-8')
            reponsexml = ET.fromstring(reponse)
            return reponsexml

    def get_nombre_resultats(self):
        
        if self.result.findall("sru:numberOfRecords",ns):
            return self.result.find("sru:numberOfRecords",ns).text
        else : 
            return 0
    
    def get_mmsId(self):
            return self.result.find("sru:records/sru:record/sru:recordIdentifier",ns).text
            
# #Gestion des erreurs
# class HTTPError(Exception):

#     def __init__(self, response, service):
#         super(HTTPError,self).__init__(self.msg(response, service))

#     def msg(self, response, service):
#         logger = logging.getLogger(service)
#         msg = "\n  HTTP Status: {}\n  Method: {}\n  URL: {}\n  Response: {}"
#         sujet = service + 'Erreur'
#         message = mail.Mail()
#         message.envoie(os.getenv('ADMIN_MAIL'),os.getenv('ADMIN_MAIL'),sujet, msg.format(response.status_code, response.request.method, response.url, response.text) )
#         logger.error("HTTP Status: {} || Method: {} || URL: {} || Response: {}".format(response.status_code, response.request.method,
#                           response.url, response.text))