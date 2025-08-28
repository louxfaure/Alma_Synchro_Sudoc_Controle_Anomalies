#!/usr/bin/python3
# -*- coding: utf-8 -*-
# from Alma_Apis_Interface import 
import json
import os
import re
from datetime import date, timedelta
import logging
import logs
import ErreursSudoc
import AlmaSru
import AlmaApi
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

SERVICE = "Alma_SUDOC_Controle_des_anomalies_de_Synchro"
ILN = '15'
INSTANCE = 'Prod'
INSTITUTIONS_LIST = {   
                        'UB' : '335229910',
                        'UBM' : '335229909',
                        'IEP' : '335229907' 
                        }
TIME_DELTA = 1
LIST_ERROR_ADM = []

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER_UB")
SMTP_PORT = int(os.getenv("SMTP_PORT_UB", 587))
EMAIL_SENDER = os.getenv("MAILTO")
EMAIL_LOGIN = os.getenv("MAIL_LOGIN_UB")
EMAIL_PASSWORD = os.getenv("MAIL_PWD_UB")
EMAIL_RECEIVER = os.getenv("MAILTO")


#On initialise le logger
logs.init_logs(os.getenv('LOGS_PATH'),SERVICE,'DEBUG')
logger = logging.getLogger(SERVICE)

# Envoi d'email
def send_email(subject, body, attachment=None):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    if attachment:
        with open(attachment, "rb") as att:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(att.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename={os.path.basename(attachment)}")
        msg.attach(part)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_LOGIN, EMAIL_PASSWORD)
        server.send_message(msg)



date_traitement = date.today() - timedelta(days=TIME_DELTA)
logger.debug(date_traitement)
for institution, rcr in INSTITUTIONS_LIST.items():
    logger.info("{} --> {}".format(institution,rcr))
    # On récupère la clef d'API
    api_key = ""
    if INSTANCE == 'Test' :
        api_key = os.getenv("TEST_{}_API".format(institution))
    else :
        api_key = os.getenv("PROD_{}_BIB_API".format(institution))
    # On récupère la liste des erreurs
    erreurs = ErreursSudoc.ErreursSudoc(ILN,rcr,date_traitement,SERVICE)
    if erreurs.status == 'Error':
        logger.error(" {} :: Impossible d'obtenir la liste des erreurs :: {}".format(institution,erreurs.error_msg))
        LIST_ERROR_ADM.append(" {} :: Impossible d'obtenir la liste des erreurs :: {}".format(institution,erreurs.error_msg))
    for erreur in erreurs :
        logger.debug(erreur)
        # Si l'erreur est à signaler aux catalogeurs on ajoute un reminder à la notice Alma
        if erreur["envoi_reseau"] :
            # On récupère l'identifiant su portfolio
            pid_extract = re.search('oai.alma..*?:(.*)', erreur["portfolio"], re.IGNORECASE)
            if not pid_extract :
                logger.error(" {} :: Impossible d'extraire le PID dans la chaine :: {}".format(institution,erreur["portfolio"]))
                LIST_ERROR_ADM.append(" {} :: Impossible d'extraire le PID dans la chaine :: {}".format(institution,erreur["portfolio"]))
                continue
            pid = pid_extract.group(1)
            logger.debug(pid)
            result = AlmaSru.AlmaSru(pid, 'alma.portfolio_pid',institution = institution,service= SERVICE,instance=INSTANCE)
            if not result.status :
                logger.error(" {} :: Portfolio inconnu ou service indisponibble :: {} :: {}".format(institution,erreur["portfolio"],result.error_msg))
                LIST_ERROR_ADM.append(" {} :: Portfolio inconnu ou service indisponibble :: {} :: {}".format(institution,erreur["portfolio"],result.error_msg))
                continue
            mmsid = result.get_mmsId()
            logger.debug(mmsid)
            # On regarde si l'erreur n'a pas déjà été signalé dans Alma
            record = AlmaApi.AlmaRecords(api_key,'EU',SERVICE)
            status_check_reminder, checkreminder = record.check_reminder(mmsid,erreur['categorie'])
            if status_check_reminder == "Error" :
                logger.error(" {} :: {} Echec sur la requête check_reminder :: {}".format(institution, mmsid ,checkreminder))
                LIST_ERROR_ADM.append(" {} :: {} Echec sur la requête check_reminder :: {}".format(institution, mmsid ,checkreminder))
                continue
            if checkreminder :
                logger.info("{} :: NOTE DEJA CREE POUR CETTE ERREUR  :: {} :: {}".format(erreur["portfolio"][-16:],erreur['code_abes'],mmsid))
                continue
            # On créé le reminder
            msg = "PPN : {}\nPId : {} \n Message : {}".format(erreur["ppn"], erreur["portfolio"][-16:], erreur["note"])
            status_create_reminder, reponse = record.create_reminder(mmsid,erreur['categorie'],msg)
            if status_create_reminder == "Error" :
                logger.error(" {} :: {} Echec sur la requête create_reminder :: {}".format(institution, mmsid,reponse))
                LIST_ERROR_ADM.append(" {} :: {} Echec sur la requête create_reminder :: {}".format(institution, mmsid,reponse))
            logger.info("{} :: NOTE CREE AVEC SUCCES :: {} ".format(mmsid,erreur['code_abes']))
        else :
            logger.info("{} :: NON SIGNALEE AU RESEAU :: {} ".format(erreur["portfolio"][-16:],erreur['code_abes']))
            LIST_ERROR_ADM.append(" {} :: {} :: {}".format(institution, erreur['code_abes'] , erreur['note']))
# Envoi du rapport d'erreur à l'administrateur
if len(LIST_ERROR_ADM) > 0:
    subject = "Contrôle de la création des inventaires dans le SUDOC : ERREURS DETECTEES"
    body = f"{len(LIST_ERROR_ADM)} inventaires n'ont pas pu être créées. Voici le détail :\n\n" + "\n".join(LIST_ERROR_ADM)
    send_email(subject, body)
else:
    subject = "Contrôle de la création des inventaires dans le SUDOC : TUDO BEM"
    body = "Aucune anomalie n'a été détectée."
    send_email(subject, body)
