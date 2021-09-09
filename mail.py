#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

__maillogin__ = os.getenv('MAIL_LOGIN')
__mailpwd__ = os.getenv('MAIL_PWD')
__smtpserver__ = os.getenv('SMTP_SERVER')
__smtpport__ = os.getenv('SMTP_PORT')

class Mail(object):

    def __init__(self, maillogin=__maillogin__, mailpwd=__mailpwd__,smtpserver=__smtpserver__,smtpport=__smtpport__):
        self.logger = logging.getLogger()
        if maillogin is None:
            raise Exception("Fournir un login ENT")
        if mailpwd is None:
            raise Exception("Fournir un mot de passe ENT")
        if smtpserver is None:
            raise Exception("Fournir un serveur SMTP")
        if smtpport is None:
            raise Exception("Fournir un port")
        self.maillogin = maillogin
        self.mailpwd = mailpwd
        self.smtpserver=smtpserver
        self.smtpport=smtpport
        
    def envoie(self, mailfrom, mailto, subject, text):
        msg = MIMEMultipart()
        msg['From'] = mailfrom
        msg['To'] = mailto
        msg['Subject'] = subject 
        msg.attach(MIMEText(text))
        mailserver = smtplib.SMTP_SSL(self.smtpserver, self.smtpport)
        mailserver.login(self.maillogin, self.mailpwd)
        mailserver.sendmail(mailfrom, mailto, msg.as_string())
        mailserver.quit()
        return "Message envoyé"