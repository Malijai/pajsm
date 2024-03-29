#-*- coding: utf-8 -*-
from __future__ import unicode_literals
import datetime
import random
import hashlib
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
# from django.db.models import Q, Count
from django.shortcuts import render, redirect
from etude.models import Questionnaire, Intervenant, Resultatenquete, Vignette, Questionpajsm, Centresante
# from .saisie import genere_questions
from etude.etude_constants import TEXTES_MESSAGES
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
# from django.utils.translation import ugettext_lazy as _
from django.core import mail
from django.db.models import Q, Count, Sum


def genere_questions_e(qid):
    questionstoutes = Questionpajsm.objects.filter(questionnaire__id=qid)
    enfants = questionstoutes.select_related('typequestion', 'parent').filter(questionpajsm__parent__id__gt=1)
    ascendancesM = {rquestion.id for rquestion in questionstoutes.select_related('typequestion').filter(pk__in=enfants)}
    ascendancesF = set()  # liste sans doublons
    compte = 0
    for rquestion in questionstoutes:
        if rquestion.typequestion.nom != 'TITLE' and rquestion.typequestion.nom != 'COMMENT' \
                 and rquestion.typequestion.nom != 'DUREE' and rquestion.parent_id == 1:
            compte += 1
        for fille in questionstoutes.select_related('typequestion').filter(parent__id=rquestion.id):
            # #va chercher si a des filles (question_ fille)
            ascendancesF.add(fille.id)
    return ascendancesF, ascendancesM, questionstoutes, compte


def inscription_intervenant(request, cissid):
    # Pour les cas ou les personnes rentrent une adresse de courriel et n'ont pas le lien:
    # Vérifie si la personne existe, et l'état d'avancement du questionnaire
    # Si n'existe pas crée une entrée et envoie un courriel avec le lien
    sonciusss = Centresante.objects.get(pk=cissid)
    if request.method == 'POST':
        courriel = request.POST.get('courriel')
        codemd5 = hashlib.md5(courriel.encode())
        code = codemd5.hexdigest()
        # code = 'A' + str(hash(courriel))
        if Intervenant.objects.filter(code=code).exists():
            intervenant = Intervenant.objects.get(code=code)
            if intervenant.completed == 1:
                message = TEXTES_MESSAGES['Rejet1']
                messages.add_message(request, messages.WARNING, message)
                return render(request, 'rejet.html')
            elif intervenant.concented == 2:
                message = TEXTES_MESSAGES['Rejet1']
                messages.add_message(request, messages.WARNING, message)
                return render(request, 'rejet.html')
            else:
                lienenquete = settings.ENTREE_URL + intervenant.code
                sujet = u"Rappel du lien pour participer à l'enquête sur les Programmes d’accompagnement en justice et santé mentale"
                message = TEXTES_MESSAGES['AR'] + intervenant.courriel + TEXTES_MESSAGES['AR2']
                lien = lienenquete
                if intervenant.centresante_id == 3:
                    lienpdf = settings.BASE_URL + settings.STATIC_URL + 'etude/FCSIV2-2Generique.pdf'
                elif intervenant.centresante_id == 19:
                    lienpdf = settings.BASE_URL + settings.STATIC_URL + 'etude/CHUMFinalConv_20210831.pdf'
                else:
                    lienpdf = settings.BASE_URL + settings.STATIC_URL + 'etude/FCSIV2.2.pdf'
                envoi_courriel(sujet, lien, lienpdf, intervenant.courriel)
                messages.add_message(request, messages.WARNING, message)
                return render(request, 'rejet.html')
        else:
            # code = 'A' + str(hash(courriel))
            codemd5 = hashlib.md5(courriel.encode())
            code = codemd5.hexdigest()
            intervenant = Intervenant.objects.create(
                courriel=courriel,
                code=code,
                centresante=sonciusss
            )
            lienenquete = settings.ENTREE_URL + code
            sujet = u"Lien pour participer à l'enquête sur les Programmes d’accompagnement en justice et santé mentale"
            message = TEXTES_MESSAGES['AR'] + intervenant.courriel + TEXTES_MESSAGES['AR2']
            if intervenant.centresante_id == 3:
                lienpdf = settings.BASE_URL + settings.STATIC_URL + 'etude/FCSIV2-2Generique.pdf'
            elif intervenant.centresante_id == 19:
                lienpdf = settings.BASE_URL + settings.STATIC_URL + 'etude/CHUMFinalConv_20210831.pdf'
            else:
                lienpdf = settings.BASE_URL + settings.STATIC_URL + 'etude/FCSIV2.2.pdf'
            lien = lienenquete
            envoi_courriel(sujet, lien, lienpdf, intervenant.courriel)
            messages.add_message(request, messages.WARNING, message)
            return render(request, 'rejet.html')

    return render(request, 'inscription.html',{'cissid': sonciusss})


def accord_intervenant(request, iid):
    if Intervenant.objects.filter(code=iid).exists():
        intervenant = Intervenant.objects.get(code=iid)
        if intervenant.concented == 1 and intervenant.completed == 0:
            if int(intervenant.partie1) == 0:
                return redirect(saveenquete,
                                intervenant.code,
                                101
                                )
            else:  # Continuer en fonction de ce qui est enregistre
                # clef: ordre, connait, implique, avocat,(p1,p2,p3,p4,p5
                # Suivantfait original
                suivantfait = {(1, 1, 1, 0, (1, 0, 0, 0, 0)): 102,
                               (1, 1, 1, 0, (1, 1, 0, 0, 0)): 103,
                               (1, 1, 1, 0, (1, 1, 1, 0, 0)): 104,
                               (1, 1, 1, 0, (1, 1, 1, 1, 0)): 105,
                               (1, 1, 0, 0, (1, 0, 0, 0, 0)): 102,
                               (1, 1, 0, 0, (1, 1, 0, 0, 0)): 104,
                               (1, 1, 0, 0, (1, 1, 0, 1, 0)): 105,
                               (1, 0, 0, 0, (1, 0, 0, 0, 0)): 104,
                               (1, 0, 0, 0, (1, 0, 0, 1, 0)): 105,
                               (1, 1, 1, 1, (1, 0, 0, 0, 0)): 102,
                               (1, 1, 1, 1, (1, 1, 0, 0, 0)): 103,
                               (1, 1, 1, 1, (1, 1, 1, 0, 0)): 104,
                               (1, 1, 1, 1, (1, 1, 1, 1, 0)): 105,
                               (1, 1, 1, 1, (1, 1, 1, 1, 1)): 106,
                               (1, 1, 0, 1, (1, 0, 0, 0, 0)): 102,
                               (1, 1, 0, 1, (1, 1, 0, 0, 0)): 104,
                               (1, 1, 0, 1, (1, 1, 0, 1, 0)): 105,
                               (1, 1, 0, 1, (1, 1, 0, 1, 1)): 106,
                               (1, 0, 0, 1, (1, 0, 0, 0, 0)): 104,
                               (1, 0, 0, 1, (1, 0, 0, 1, 0)): 105,
                               (1, 0, 0, 1, (1, 0, 0, 1, 1)): 106,
                               (2, 1, 1, 0, (1, 0, 0, 0, 0)): 105,
                               (2, 1, 1, 0, (1, 0, 0, 0, 1)): 102,
                               (2, 1, 1, 0, (1, 1, 0, 0, 1)): 103,
                               (2, 1, 1, 0, (1, 1, 1, 0, 1)): 104,
                               (2, 1, 0, 0, (1, 0, 0, 0, 0)): 105,
                               (2, 1, 0, 0, (1, 0, 0, 0, 1)): 102,
                               (2, 1, 0, 0, (1, 1, 0, 0, 1)): 104,
                               (2, 0, 0, 0, (1, 0, 0, 0, 0)): 105,
                               (2, 0, 0, 0, (1, 0, 0, 0, 1)): 104,
                               (2, 1, 1, 1, (1, 0, 0, 0, 0)): 105,
                               (2, 1, 1, 1, (1, 0, 0, 0, 1)): 102,
                               (2, 1, 1, 1, (1, 1, 0, 0, 1)): 103,
                               (2, 1, 1, 1, (1, 1, 1, 0, 1)): 104,
                               (2, 1, 1, 1, (1, 1, 1, 1, 1)): 106,
                               (2, 1, 0, 1, (1, 0, 0, 0, 0)): 105,
                               (2, 1, 0, 1, (1, 0, 0, 0, 1)): 102,
                               (2, 1, 0, 1, (1, 1, 0, 0, 1)): 104,
                               (2, 1, 0, 1, (1, 1, 0, 1, 1)): 106,
                               (2, 0, 0, 1, (1, 0, 0, 0, 0)): 105,
                               (2, 0, 0, 1, (1, 0, 0, 0, 1)): 104,
                               (2, 0, 0, 1, (1, 0, 0, 1, 1)): 106,
                               }
                try:
                    qid = suivantfait[intervenant.ordre, intervenant.connait, intervenant.implique, intervenant.avocat,
                                      (int(intervenant.partie1), int(intervenant.partie2), int(intervenant.partie3),
                                       int(intervenant.partie4), int(intervenant.partie5))]
                except Exception:
                    message = TEXTES_MESSAGES['Erreur']
                    messages.add_message(request, messages.ERROR, message)
                    return render(request, 'rejet.html')
                return redirect(saveenquete,
                                intervenant.code,
                                qid,
                                )
        elif intervenant.concented == 1 and intervenant.completed == 1:
            message = TEXTES_MESSAGES['Complet1']
            messages.add_message(request, messages.ERROR, message)
            return render(request, 'rejet.html')
        elif intervenant.concented == 0:
            # Proceder au consentement
            return suite_accord(request, intervenant.code)
        elif intervenant.concented == 2:
            message = TEXTES_MESSAGES['Refus2']
            messages.add_message(request, messages.ERROR, message)
            return render(request, 'rejet.html')
    else:
        return redirect('accueil')


def suite_accord(request, iid):
    intervenant = Intervenant.objects.get(code=iid)
    sonciusss = Centresante.objects.get(pk=intervenant.centresante_id)
    # Intervenant reconnu doit consentir a participer.
    # L ordre et les vignettes sont assignees a ce moment la
    if request.method == 'POST':
        if request.POST.get('accord') == 'Consent':
            if request.POST.get('utilisationsecondaire'):
                utilisationsecondaire = request.POST.get('utilisationsecondaire')
            else:
                utilisationsecondaire = 0
            if request.POST.get('efutures'):
                efutures = request.POST.get('efutures')
            else:
                efutures = 0
            if request.POST.get('tirage'):
                tirage = request.POST.get('tirage')
            else:
                tirage = 0
            ordre = random.randint(1, 2)
            vignette1 = random.randint(1, 16)
            vignette2 = random.randint(17, 32)
            intervenant.concented = 1
            intervenant.utilisationsecondaire = utilisationsecondaire
            intervenant.contactfutur = efutures
            intervenant.tirage = tirage
            intervenant.ordre = ordre
            intervenant.vignette1 = vignette1
            intervenant.vignette2 = vignette2
            intervenant.date_consentement = datetime.datetime.now()
            intervenant.save()
            texte = TEXTES_MESSAGES['Consent']
            messages.add_message(request, messages.ERROR, texte)
            return redirect(saveenquete,
                                    intervenant.code,
                                    101,
                                    )
        elif request.POST.get('accord') == "Refuser":
            intervenant.concented = 2
            # intervenant.courriel = "refus"
            intervenant.save()
            message = TEXTES_MESSAGES['Refus1']
            messages.add_message(request, messages.ERROR, message)
            return render(request, 'rejet.html')

    return render(request, 'accord.html', {'intervenant': intervenant, 'sonciusss': sonciusss})


def saveenquete(request, cid, qid):
    # genere le questionnaire en fonction de l ordre, de la reponse a certaines questions
    # et des vignettes tirees au sort
    complete = {
        101: 'partie1',
        102: 'partie2',
        103: 'partie3',
        104: 'partie4',
        105: 'partie5',
        106: 'partie6',
    }
    condition = {
        'CN28': 'implique',
        'ID8': 'connait',
        'ID7': 'avocat',
    }
    # clef: ordre, connait, implique, avocat (sont les seuls qui font le 106)
    suivant = {(1, 1, 1, 0): {101: 102, 102: 103, 103: 104, 104: 105, 105: 110},
               (1, 1, 0, 0): {101: 102, 102: 104, 104: 105, 105: 110},
               (1, 0, 0, 0): {101: 104, 104: 105, 105: 110},
               (1, 1, 1, 1): {101: 102, 102: 103, 103: 104, 104: 105, 105: 106, 106: 110},
               (1, 1, 0, 1): {101: 102, 102: 104, 104: 105, 105: 106, 106: 110},
               (1, 0, 0, 1): {101: 104, 104: 105, 105: 106, 106: 110},
               (2, 1, 1, 0): {101: 105, 105: 102, 102: 103, 103: 104, 104: 110},
               (2, 1, 0, 0): {101: 105, 105: 102, 102: 104, 104: 110},
               (2, 0, 0, 0): {101: 105, 105: 104, 104: 110},
               (2, 1, 1, 1): {101: 105, 105: 102, 102: 103, 103: 104, 104: 106, 106: 110},
               (2, 1, 0, 1): {101: 105, 105: 102, 102: 104, 104: 106, 106: 110},
               (2, 0, 0, 1): {101: 105, 105: 104, 104: 106, 106: 110},
               }

    # clef: ordre, connait, implique, avocat,(p1,p2,p3,p4,p5)
    # p1=101 = identification nb questions= 8
    # p2=102 = connaissance nb questions= 29
    # p3=103 = implantation nb questions= 32
    # p4=104 = vignettes nb questions= 28
    # p5= 105 = perception1 nb questions= 11
    # p6=106 = perception2 (avocats) nb questions= 7
    nbsuivant = {(1, 1, 1, 0, (1, 0, 0, 0, 0)): 8 / 108,
                 (1, 1, 1, 0, (1, 1, 0, 0, 0)): 37 / 108,
                 (1, 1, 1, 0, (1, 1, 1, 0, 0)): 69 / 108,
                 (1, 1, 1, 0, (1, 1, 1, 1, 0)): 97 / 108,
                 (1, 1, 0, 0, (1, 0, 0, 0, 0)): 8 / 76,
                 (1, 1, 0, 0, (1, 1, 0, 0, 0)): 37 / 76,
                 (1, 1, 0, 0, (1, 1, 0, 1, 0)): 65 / 76,
                 (1, 0, 0, 0, (1, 0, 0, 0, 0)): 8 / 47,
                 (1, 0, 0, 0, (1, 0, 0, 1, 0)): 26 / 47,
                 (1, 1, 1, 1, (1, 0, 0, 0, 0)): 8 / 115,
                 (1, 1, 1, 1, (1, 1, 0, 0, 0)): 37 / 115,
                 (1, 1, 1, 1, (1, 1, 1, 0, 0)): 69 / 115,
                 (1, 1, 1, 1, (1, 1, 1, 1, 0)): 97 / 115,
                 (1, 1, 1, 1, (1, 1, 1, 1, 1)): 108 / 115,
                 (1, 1, 0, 1, (1, 0, 0, 0, 0)): 8 / 83,
                 (1, 1, 0, 1, (1, 1, 0, 0, 0)): 37 / 83,
                 (1, 1, 0, 1, (1, 1, 0, 1, 0)): 65 / 83,
                 (1, 1, 0, 1, (1, 1, 0, 1, 1)): 76 / 83,
                 (1, 0, 0, 1, (1, 0, 0, 0, 0)): 8 / 54,
                 (1, 0, 0, 1, (1, 0, 0, 1, 0)): 36 / 54,
                 (1, 0, 0, 1, (1, 0, 0, 1, 1)): 43 / 54,
                 (2, 1, 1, 0, (1, 0, 0, 0, 0)): 8 / 108,
                 (2, 1, 1, 0, (1, 0, 0, 0, 1)): 19 / 108,
                 (2, 1, 1, 0, (1, 1, 0, 0, 1)): 48 / 108,
                 (2, 1, 1, 0, (1, 1, 1, 0, 1)): 80 / 108,
                 (2, 1, 0, 0, (1, 0, 0, 0, 0)): 8 / 76,
                 (2, 1, 0, 0, (1, 0, 0, 0, 1)): 19 / 76,
                 (2, 1, 0, 0, (1, 1, 0, 0, 1)): 48 / 76,
                 (2, 0, 0, 0, (1, 0, 0, 0, 0)): 8 / 47,
                 (2, 0, 0, 0, (1, 0, 0, 0, 1)): 19 / 47,
                 (2, 1, 1, 1, (1, 0, 0, 0, 0)): 8 / 115,
                 (2, 1, 1, 1, (1, 0, 0, 0, 1)): 19 / 115,
                 (2, 1, 1, 1, (1, 1, 0, 0, 1)): 48 / 115,
                 (2, 1, 1, 1, (1, 1, 1, 0, 1)): 80 / 115,
                 (2, 1, 1, 1, (1, 1, 1, 1, 1)): 108 / 115,
                 (2, 1, 0, 1, (1, 0, 0, 0, 0)): 8 / 83,
                 (2, 1, 0, 1, (1, 0, 0, 0, 1)): 19 / 83,
                 (2, 1, 0, 1, (1, 1, 0, 0, 1)): 48 / 83,
                 (2, 1, 0, 1, (1, 1, 0, 1, 1)): 76 / 83,
                 (2, 0, 0, 1, (1, 0, 0, 0, 0)): 8 / 54,
                 (2, 0, 0, 1, (1, 0, 0, 0, 1)): 19 / 54,
                 (2, 0, 0, 1, (1, 0, 0, 1, 1)): 43 / 54,
                 }

    intervenant = Intervenant.objects.get(code=cid)
    vignette1 = Vignette.objects.get(id=intervenant.vignette1)
    vignette2 = Vignette.objects.get(id=intervenant.vignette2)
    questionnaire = Questionnaire.objects.get(id=qid)
    ascendancesF, ascendancesM, questionstoutes, compte = genere_questions_e(qid)
    if qid == 101:
        nbfait = 0
    else:
        nbfait = nbsuivant[intervenant.ordre, intervenant.connait, intervenant.implique, intervenant.avocat,
                           (int(intervenant.partie1), int(intervenant.partie2), int(intervenant.partie3),
                            int(intervenant.partie4), int(intervenant.partie5))]
        nbfait = nbfait * 100
    if request.method == 'POST':
        if 'suite' in request.POST and qid != 110:
             # print('NB questions - ', compte)
            reponses = []
            for question in questionstoutes:
                if question.parent_id == 1:
                    reponseaquestion = request.POST.get('q' + str(question.id))
                    if reponseaquestion:
                        reponses.append(reponseaquestion)
             # print('NB reponses - ', len(reponses))
            posees = compte
            repondues = len(reponses)
            if posees - repondues > 0:
                message = TEXTES_MESSAGES['Vides']
                messages.add_message(request, messages.INFO, message)
                return render(request, 'rejet.html')
            for question in questionstoutes:
                if question.typequestion.nom == 'DUREE':
                    an = request.POST.get('q{}_year'.format(question.id))
                    mois = request.POST.get('q{}_month'.format(question.id))
                    jour = request.POST.get('q{}_day'.format(question.id))
                    reponseaquestion = "{}ans-{}mois-{}jours".format(an, mois, jour)
                else:
                    reponseaquestion = request.POST.get('q' + str(question.id))
                # print(question.id, ' - ', question.varname, ' + ', reponseaquestion)
                if reponseaquestion:
                    if not Resultatenquete.objects.filter(intervenant_id=intervenant.id, question=question,
                                                          reponsetexte=reponseaquestion).exists():
                        Resultatenquete.objects.update_or_create(intervenant_id=intervenant.id,
                                                                 questionnaire=questionnaire, question=question,
                                                                 defaults={
                                                                     'reponsetexte': reponseaquestion,
                                                                 }
                                                                 )
                    if question.varname in condition.keys():
                        if int(reponseaquestion) == 1 or int(reponseaquestion) == 2:
                            reponse = 1
                        else:
                            reponse = 0
                        intervenant.__dict__[condition[question.varname]] = reponse
                        intervenant.save()
            now = datetime.datetime.now().strftime('%H:%M:%S')
            old_qid = int(request.POST.get('qid'))
            new_qid = old_qid
            if (intervenant.ordre, intervenant.connait, intervenant.implique, intervenant.avocat) in suivant:
                messages.add_message(request, messages.WARNING, u'Enregistre a ' + now)
                intervenant.__dict__[complete[old_qid]] = 1
                intervenant.save()
                new_qid = suivant[(intervenant.ordre, intervenant.connait, intervenant.implique, intervenant.avocat)][
                    old_qid]
                #                ascendancesF, ascendancesM, questionstoutes = genere_questions(new_qid)
                #                questionnaire = Questionnaire.objects.get(id=new_qid)
                qid = new_qid
            else:
                message = TEXTES_MESSAGES['Incompatible']
                messages.add_message(request, messages.ERROR, message)
            if new_qid == 110:
                intervenant.completed = 1
                # intervenant.courriel = "termine"
                intervenant.save()
                message = TEXTES_MESSAGES['Termine']
                messages.add_message(request, messages.ERROR, message)
                return render(request, 'rejet.html')
            return redirect(saveenquete,
                            cid,
                            qid,
                            )
        elif qid == 110:
            message = TEXTES_MESSAGES['Termine2']
            messages.add_message(request, messages.ERROR, message)
            return render(request, 'rejet.html')
    else:
        # print('qid - ', qid, ' - ')
        return render(request, 'saveenquete.html',
                      {
                          'qid': qid,
                          'questions': questionstoutes,
                          'ascendancesM': ascendancesM,
                          'ascendancesF': ascendancesF,
                          'questionnaire': questionnaire,
                          'intervenant': intervenant,
                          'range': range(1, int(questionnaire.description) + 1),
                          'vignette1': vignette1,
                          'vignette2': vignette2,
                          'nbfait': nbfait,
                      }
                      )


def envoi_courriel_new(sujet, lien, lienpdf, courriel):
    html_message = render_to_string('mail.html', {'lien': lien, 'lienpdf': lienpdf })
    plain_message = strip_tags(html_message)
    from_email = settings.DEFAULT_FROM_EMAIL
    to = courriel
    #mail.send_mail(sujet, plain_message, from_email, [to], html_message=html_message)
    msg = EmailMultiAlternatives(sujet, plain_message, from_email, [to])
    msg.attach_alternative(html_message, "text/html")
    msg.send()


def envoi_courriel(sujet, lien, lienpdf, courriel):
    # (sujet, textecourriel, courriel)
    html_message = render_to_string('mail.html', {'lien': lien, 'lienpdf': lienpdf })
    textecourriel = strip_tags(html_message)
    with mail.get_connection() as connection:
        mail.EmailMessage(
            sujet, textecourriel, 'malijai.caulet@ntp-ptn.org', [courriel],
            connection=connection,
        ).send()


@login_required(login_url=settings.LOGIN_URI)
def bilan_sondage(request):
    questionnaires = Questionnaire.objects.filter(Q(id__gt=100) & Q(id__lt=107))

    if 'Exporterdata' in request.POST:
        questionnaire = request.POST.get('questionnaireid')
        chose = request.POST.get('tous')
        if chose == "1":
            tous = 1
        else:
            tous = 0
        return redirect('prepare_csv', questionnaire=questionnaire, tous=tous)
    elif 'fait_entete_pajinter_R' in request.POST:
        questionnaire = request.POST.get('questionnaireid')
        return redirect('fait_entete_pajinter_R', questionnaire=questionnaire)
    else:
        nb_par_ciusss = Intervenant.objects.values('centresante').order_by('centresante') \
            .annotate(completed=Sum('completed'), concented=Sum('concented'), avocat=Sum('avocat'))
        ciusss = Centresante.objects.all()
        touslesresultats = []
        sommes = Intervenant.objects.filter(Q(concented=1)).aggregate(SCp=Sum('completed'), Sp1=Sum('partie1'), Sp2=Sum('partie2'), Sp3=Sum('partie3'), Sp4=Sum('partie4'), Sp5=Sum('partie5'), Sp6=Sum('partie6'))

        for cisss in ciusss:
            ligneMH = []
            if Intervenant.objects.filter(centresante=cisss.id).exists():
                nb_par_ciusss = Intervenant.objects.values('centresante').filter(Q(centresante=cisss.id)).order_by('centresante') \
                    .annotate(completed=Sum('completed'), inscrit=Count('concented'), concent=Count('concented', filter=Q(concented=1)),
                              avocat=Sum('avocat'), refusent=Count('concented', filter=Q(concented=2)),
                              ordre1=Count('ordre', filter=Q(ordre=1)), ordre2=Count('ordre', filter=Q(ordre=2)),
                              p1=Count('partie1', filter=Q(partie1=1)),p2=Count('partie2', filter=Q(partie2=1)),p3=Count('partie3', filter=Q(partie3=1)),
                              p4=Count('partie4', filter=Q(partie4=1)),p5=Count('partie5', filter=Q(partie5=1)),p6=Count('partie6', filter=Q(partie6=1)))
                ligneMH.append(cisss.nom)
                ligneMH.append(nb_par_ciusss[0]['completed'])
                ligneMH.append(nb_par_ciusss[0]['concent'])
                ligneMH.append(nb_par_ciusss[0]['avocat'])
                ligneMH.append(nb_par_ciusss[0]['inscrit'])
                ligneMH.append(nb_par_ciusss[0]['refusent'])
                ligneMH.append(nb_par_ciusss[0]['ordre1'])
                ligneMH.append(nb_par_ciusss[0]['ordre2'])
                ligneMH.append(nb_par_ciusss[0]['p1'])
                ligneMH.append(nb_par_ciusss[0]['p2'])
                ligneMH.append(nb_par_ciusss[0]['p3'])
                ligneMH.append(nb_par_ciusss[0]['p4'])
                ligneMH.append(nb_par_ciusss[0]['p5'])
                ligneMH.append(nb_par_ciusss[0]['p6'])
            if len(ligneMH) != 0:
                touslesresultats.append(ligneMH)

        return render(
                request,
                'bilan.html',
                {
                    'complets': touslesresultats,
                    'questionnaires': questionnaires,
                    'sommes': sommes,
                }
            )


