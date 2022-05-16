import re
# external imports
import requests
import logging
import xml.etree.ElementTree as ET
# internal import
from datetime import datetime


class ErreursSudoc(object):
    """
    EreursSUDOC
    =======
    Appel une procédure stockée du SUDOC qui renvoie une liste d'anomalie      
"""

    def __init__(self,iln,rcr,date_traitement,service=__name__):
        self.logger = logging.getLogger(service)
        self.url = "https://www.sudoc.fr/services/generic/?servicekey=Alma_Synthese&iln={}&rcr={}&format=application/xml".format(iln,rcr)
        self.index = -1
        self.errors_list = [{'code_abes' : 'Lien erroné',
                            'pattern' : 'Lien .{9} erroné',
                            'note' : 'Une des zones de lien pointe vers une notice ayant un code support non  adapté au type de lien',
                            'envoi_admin' : False,
                            'envoi_reseau' : True,
                            'categorie' : 'BAD_LINK'},
                            {'code_abes' : 'Notice non localisée ',
                            'pattern' : 'Notice non localisée',
                            'note' : "L'OAI renvoie une demande de suppression sur une notice déjà supprimée",
                            'envoi_admin' : True,
                            'envoi_reseau' : False,
                            'categorie' : ''},
                            {'code_abes' : 'Problème de validation au niveau bibliographique de la notice',
                            'pattern' : 'Problème de validation au niveau bibliographique de la notice',
                            'note' : 'Une erreur de catalogage sur la notice empeche la création de l''exemplaire.',
                            'envoi_admin' : False,
                            'envoi_reseau' : True,
                            'categorie' : 'REVISION'},
                            {'code_abes' : 'Pb. structure 955',
                            'pattern' : 'La zone 231@\/01 ',
                            'note' : 'Plusieurs 955 dans l’inventaire envoyé',
                            'envoi_admin' : True,
                            'envoi_reseau' : False,
                            'categorie' : ''},
                            {'code_abes' : 'La zone E856 ne peut être ajoutée que pour le type de document O ou Z',
                            'pattern' : 'La zone E856 ne peut être ajoutée que pour le type de document O ou Z',
                            'note' : 'Dans Alma un PPN de document imprimé a été ajouté à la notice électronique',
                            'envoi_admin' : False,
                            'envoi_reseau' : True,
                            'categorie' : 'BAD_PPN'},
                            {'code_abes' : 'La notice est supprimée',
                            'pattern' : 'La notice est supprimée',
                            'note' : 'La PPN affecté à la notice est un PPN d’une notice qui a été fusionnée',
                            'envoi_admin' : False,
                            'envoi_reseau' : True,
                            'categorie' : 'PPN_DELETED'},
                            {'code_abes' : 'FATAL ERROR',
                            'pattern' : 'FATAL ERROR, see errorlog',
                            'note' : '',
                            'envoi_admin' : False,
                            'envoi_reseau' : False,
                            'categorie' : ''},
                            {'code_abes' : 'Exemplaire ABES trop ancien ou revenu (boucle) par oai, date record:',
                            'pattern' : 'Exemplaire ABES trop ancien ou revenu',
                            'note' : '',
                            'envoi_admin' : False,
                            'envoi_reseau' : False,
                            'categorie' : ''},
                            {'code_abes' : 'Notice protégée en écriture',
                            'pattern' : 'Cette notice d&apos;exemplaire est protégée',
                            'note' : '',
                            'envoi_admin' : True,
                            'envoi_reseau' : False,
                            'categorie' : ''}
                ]

        self.date_traitement = date_traitement
        r = requests.get(self.url)
        self.logger.debug(self.url)

        try:
            r.raise_for_status()  
        except (requests.exceptions.HTTPError, requests.exceptions.ConnectionError):
            self.status = 'Error'
            self.logger.error("{} :: HTTP Status: {} || Method: {} || URL: {} || Response: {}".format( service, r.status_code, r.request.method, r.url, r.text))
            self.error_msg = "{} :: HTTP Status: {} || Method: {} || URL: {} || Response: {}".format( service, r.status_code, r.request.method, r.url, r.text)
        else:
            record = r.content.decode('utf-8')
            self.status = 'Succes'
            root = ET.fromstring(record)
            self.results = root.findall(".//ROW")

    def __iter__(self):
        return self
    
    def __next__(self):
        self.index += 1
        if self.index >= len(self.results):
            self.index = -1
            raise StopIteration
        else:
            # On filtre la liste pour ne récupérer que les erreurs résulantes du dernier traitement
            date_erreur = datetime.strptime(self.results[self.index].find("DATE_TRAITE").text,'%Y/%m/%d %H:%M:%S')
            if date_erreur.date() < self.date_traitement :
                self.index = -1
                raise StopIteration
            # On va voir si l'erreur est référencée etrécupérer les informations relatives au traitement attendu pour cette erreur
            erreur = self.check_erreur(self.results[self.index].find("ERROR").text)
            erreur["msg_erreur"] = self.results[self.index].find("ERROR").text
            erreur["ppn"] = self.results[self.index].find("PPN").text
            erreur["portfolio"] = self.results[self.index].find("ID").text
            erreur["date"] = date_erreur
            return erreur

    def check_erreur(self, erreur) :
        """Analyse l'erreur retournée par l'ABES et la catégorise.
        Si l'erreur n'est pas répertoriée, alerte l'administrateur

        Args:
            erreur ([txt]): message d'erreur (contenu du noeud ROW/ERROR)

        Returns:
            [dict]: 
        """
        for error in self.errors_list :
            x = re.search(error['pattern'],erreur)
            if x :
                return error
        return {'code_abes' : erreur,
                'pattern' : 'Exemplaire ABES trop ancien ou revenu',
                'note' : '',
                'envoi_admin' : True,
                'envoi_reseau' : False,
                'categorie' : ''}
