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
import mail

SERVICE = "Alma SUDOC Contrôle des anomalies"
ILN = '497'
INSTANCE = 'Test'
INSTITUTIONS_LIST = { 'BXSA' : '330009999' }
TIME_DELTA = 4
LIST_ERROR_ADM = []

#On initialise le logger
logs.init_logs(os.getenv('LOGS_PATH'),SERVICE,'DEBUG')
logger = logging.getLogger(SERVICE)

date_traitement = date.today() - timedelta(days=TIME_DELTA)
logger.debug(date_traitement)
for institution, rcr in INSTITUTIONS_LIST.items():
    logger.debug("{} --> {}".format(institution,rcr))
    # On récupère la clef d'API
    api_key = ""
    if INSTANCE == 'Test' :
        api_key = os.getenv("TEST_{}_API".format(institution))
    else :
        api_key = os.getenv("PROD_{}_BIB_API".format(institution))
    # On récupère la liste des erreurs
    erreurs = ErreursSudoc.ErreursSudoc(ILN,rcr,date_traitement,SERVICE)
    if erreurs.status == 'Error':
        LIST_ERROR_ADM.append(" {} :: Impossible d'obtenir la liste des erreurs :: {}".format(institution,erreurs.error_msg))
    for erreur in erreurs :
        # logger.debug(erreur["envoi_reseau"])
        # Si l'erreur est à siganler aux catalogeurs on ajoute un reminder à la notice Alma
        if erreur["envoi_reseau"] :
            # On récupère le MMSID
            # logger.debug(erreur["portfolio"][-16:])
            result = AlmaSru.AlmaSru(erreur["portfolio"][-16:], 'alma.portfolio_pid',institution = institution,service= SERVICE,instance=INSTANCE)
            if not result.status :
                LIST_ERROR_ADM.append(" {} :: Portfolio inconnu ou service indisponibble :: {}".format(institution,result.error_msg))
                continue
            mmsid = result.get_mmsId()
            logger.debug(mmsid)
            # On regarde si l'erreur n'a pas déjà été signalé dans Alma
            record = AlmaApi.AlmaRecords(api_key,'EU',SERVICE)
            status_check_reminder, checkreminder = record.check_reminder(mmsid,erreur['categorie'])
            if status_check_reminder == "Error" :
                LIST_ERROR_ADM.append(" {} :: {} Echec sur la requête check_reminder :: {}".format(institution, mmsid ,checkreminder))
                continue
            if checkreminder :
                continue
            # On créé le reminder
            msg = "PPN : {}\nPId : {} \n Message : {}".format(erreur["ppn"], erreur["portfolio"][-16:], erreur["note"])
            status_create_reminder, reponse = record.create_reminder(mmsid,erreur['categorie'],msg)
            if status_create_reminder == "Error" :
                LIST_ERROR_ADM.append(" {} :: {} Echec sur la requête create_reminder :: {}".format(institution, mmsid,reponse))
# Envoi du rapport d'erreur à l'administrateur
if len(LIST_ERROR_ADM) > 0 :
    msg = mail.Mail()
    msg.envoie("os.getenv('ADMIN_MAIL')","os.getenv('ADMIN_MAIL')","[{}] : erreurs rencontrées".format(SERVICE),"\n".join(LIST_ERROR_ADM))
    