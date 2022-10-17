# regularite-TER.py
# création du serveur de l'application à partir du corrigé du TD 4 : 

import http.server
import socketserver
from urllib.parse import urlparse, parse_qs, unquote
import json

import matplotlib.pyplot as plt
import datetime as dt
import matplotlib.dates as pltd
import random as rd 

import sqlite3

PORT = 8081

date_ouverture = str(dt.datetime.today())  # heure à l'ouverture du fichier Python (nécessaire pour la gestion du cache)


#
# Définition du nouveau handler
#
class RequestHandler(http.server.SimpleHTTPRequestHandler):

  # sous-répertoire racine des documents statiques
  static_dir = '/client'

  #
  # On surcharge la méthode qui traite les requêtes GET
  #
  def do_GET(self):

    # On récupère les étapes du chemin d'accès
    self.init_params()

    # le chemin d'accès commence par /time
    if self.path_info[0] == 'time':
      self.send_time()
   
     # le chemin d'accès commence par /regions
    elif self.path_info[0] == 'stations':   
      self.send_stations()    
      
    # le chemin d'accès commence par /ponctualite
    elif self.path_info[0] == 'concentration':   
      self.send_concentration()    
      
    # nouveau chemin d'accès pour afficher les polluants sélectionnés 
    elif self.path_info[0] == 'selectpol':   
      self.send_selectpol()    
      
    # nouveau chemin d'accès pour un affichage par commune 
    elif self.path_info[0] == 'commune':   
      self.send_commune()    
      
    # ou pas...
    else:
      self.send_static()

  #
  # On surcharge la méthode qui traite les requêtes HEAD
  #
  def do_HEAD(self):
    self.send_static()

  #
  # On envoie le document statique demandé
  #
  def send_static(self):

    # on modifie le chemin d'accès en insérant un répertoire préfixe
    self.path = self.static_dir + self.path

    # on appelle la méthode parent (do_GET ou do_HEAD)
    # à partir du verbe HTTP (GET ou HEAD)
    if (self.command=='HEAD'):
        http.server.SimpleHTTPRequestHandler.do_HEAD(self)
    else:
        http.server.SimpleHTTPRequestHandler.do_GET(self)
  
  #     
  # on analyse la requête pour initialiser nos paramètres
  #
  def init_params(self):
    # analyse de l'adresse
    info = urlparse(self.path)
    self.path_info = [unquote(v) for v in info.path.split('/')[1:]]  # info.path.split('/')[1:]
    self.query_string = info.query
    self.params = parse_qs(info.query)

    # récupération du corps
    length = self.headers.get('Content-Length')
    ctype = self.headers.get('Content-Type')
    if length:
      self.body = str(self.rfile.read(int(length)),'utf-8')
      if ctype == 'application/x-www-form-urlencoded' : 
        self.params = parse_qs(self.body)
    else:
      self.body = ''
   
    # traces
    print('info_path =',self.path_info)
    print('body =',length,ctype,self.body)
    print('params =', self.params)
    
    
  #
  # On envoie un document avec l'heure
  #
  def send_time(self):
    
    # on récupère l'heure
    time = self.date_time_string()

    # on génère un document au format html
    body = '<!doctype html>' + \
           '<meta charset="utf-8">' + \
           '<title>l\'heure</title>' + \
           '<div>Voici l\'heure du serveur :</div>' + \
           '<pre>{}</pre>'.format(time)

    # pour prévenir qu'il s'agit d'une ressource au format html
    headers = [('Content-Type','text/html;charset=utf-8')]

    # on envoie
    self.send(body,headers)

  #
  # On génère et on renvoie la liste des stations et leurs coordonnées : 
  # (affichage sur la carte des points d'intêret ensuite)
  #
  def send_stations(self):     
    # on renvoie les stations et leur localisation 
    conn = sqlite3.connect('bdd_projetB.db')
    c = conn.cursor()
    
    c.execute("SELECT * FROM 'stations'")
    r = c.fetchall()
    
    headers = [('Content-Type','application/json')];
    body = json.dumps([{'nom':a[3], 'lat':a[1], 'lon':a[0]} for a in r])
    self.send(body,headers)
    
    
         
  #
  # On génère et on renvoie un graphique de concentration en polluants pour une station donnée : 
  #
  def send_concentration(self):    

    conn = sqlite3.connect('bdd_projetB.db')  #
    c = conn.cursor()
    
    if len(self.path_info) <= 1 or self.path_info[1] == '' :   # pas de paramètre => liste par défaut
        # Definition des régions et des couleurs de tracé
        
        stations = []
        graphique = 'stations'
    else:
        graphique = self.path_info[1]
        # On teste que la région demandée existe bien
        c.execute("SELECT DISTINCT nom_station FROM 'moyennes-journalieres'")  # MODIF 
        reg = c.fetchall()
        if (self.path_info[1],) in reg:   # Rq: reg est une liste de tuples
          stations = [(self.path_info[1],"blue")]     # MODIF
          print(stations)
        else:
            print ('Erreur nom')
            self.send_error(404)    # Station non trouvée -> erreur 404
            return None

    
    # configuration du tracé
    fig1 = plt.figure(figsize=(18,6))
    ax = fig1.add_subplot(111)
    ax.grid(which='major', color='#888888', linestyle='-')
    ax.grid(which='minor',axis='x', color='#888888', linestyle=':')
    ax.xaxis.set_major_locator(pltd.YearLocator())
    ax.xaxis.set_minor_locator(pltd.MonthLocator())
    ax.xaxis.set_minor_locator(pltd.DayLocator())
    ax.xaxis.set_major_formatter(pltd.DateFormatter('%B %Y'))
    ax.xaxis.set_tick_params(labelsize=10)
    ax.xaxis.set_label_text("Date")
    ax.yaxis.set_label_text("Concentration de polluants")  # MODIF 

    # boucle sur les stations (on cherche à afficher la concentration de polluant sur une année pour une station donnée)
    for l in (stations) :
         
        c.execute("SELECT * FROM 'moyennes-journalieres' WHERE nom_station=? ORDER BY date_debut",l[:1]) #ou (l[0],) # MODIF 
        r = c.fetchall()
         
        # création des listes de points pour tracer le graphe : 
        # on va superposer plusieurs courbes sur le graphe en fonction du polluant représenté : 
        
        c.execute("SELECT DISTINCT(nom_poll) FROM 'moyennes-journalieres' WHERE nom_station = ?",l[:1])
        polluants = c.fetchall()
        x = [[] for i in range(len(polluants))]   # dates 
        y = [[] for i in range(len(polluants))]   # valeurs
        chgmt_mois = False
        
        for a in r : 
          
          date = (int(a[15][:4]),int(a[15][5:7]),int(a[15][8:10]))
          i = 0 
          j = 0 
          date_f = (int(a[16][:4]),int(a[16][5:7]),int(a[16][8:10])) # date de fin  
          
          #while date != date_f : # on ajoute tous les jours entre ces deux dates 
          for k in range(int(a[16][8:10])-int(a[15][8:10])) :   # revoir quel est le problème    
            if (date[1]>0 and date[1]<13) and (date[2]>0 and date[2]<31):
              if date[1] == date_f[1] and a[12] !=None:  # pas de changement de mois 
                p = a[9]
                indice = 0 
                for m in range(len(polluants)):
                  if polluants[m][0] == p:
                    indice = m
                x[indice].append(dt.date(date[0],date[1],date[2]+i))
                y[indice].append(float(a[12]))
                i +=1 
                date = (date[0],date[1],date[2]+i)
              
              else : # il y a un changement de mois 
              
                if chgmt_mois == True and a[12] !=None:
                  p = a[9]
                  indice = 0 
                  for m in range(len(polluants)):
                    if polluants[m][0] == p:
                      indice = m
                  x[indice].append(dt.date(date[0],date[1],j))
                  y[indice].append(float(a[12]))
                  date = (date[0],date[1]+1,j)
                  j += 1 
              
                else :  
                  if a[12] !=None: 
                    p = a[9]
                    indice = 0 
                    for m in range(len(polluants)):
                      if polluants[m][0] == p:
                        indice = m
                    x[indice].append(dt.date(date[0],date[1],date[2]+i))
                    y[indice].append(float(a[12]))
                  
                  if date[1]//2 == 0 and date[2] == 30 : 
                    chgmt_mois == True 
                  elif date[1]//2 != 0 and date[2] == 31 :
                    chgmt_mois == True 
                  elif date[1] == 2 and date[2] == 28 : 
                    chgmt_mois == True 
                  i +=1 
                  date = (date[0],date[1],date[2]+i)
          
            
        # tracé des courbes : 
        color = ['blue','green','red','orange','purple','pink','black']
        for m in range(len(polluants)):
          plt.plot(x[m],y[m],color[m],linewidth=1, linestyle='-', marker='o', color=color[m], label=polluants[m][0])
        
        # légendes : 
        plt.legend(loc='lower left')  
        plt.title('Concentration de polluants (en micro_g/m^3)',fontsize=16)  # MODIF
      
        
        #### Gestion du cache : 
        
        ################ Fonctions auxillaires ##########################
        def dateSuperieure(d1,d2) :
          if d1[0:4] >= d2[0:4] and d1[5:7] >= d2[5:7] and d1[8:10] >= d2[8:10]:
            return(True)
          return(False)

        def heureSuperieure(h1,h2):
          if h1[0:2] >= h2[0:2] and h1[3:5] >= h2[3:5] and h1[6:8] >= h2[6:8]:
            return(True)
          return(False)
        
        # on commence par renommer les noms des graphes : ajout de la date de création : 
        jour_heure = str(dt.datetime.today())   # de 0 à 9 inclu : la date, puis un espace (à enlever), puis de 10 à 17 inclu, l'heure
        jour = jour_heure[0:4]+'_'+jour_heure[5:7]+'_'+jour_heure[8:10]   # récupération du jour 
        heure = jour_heure[11:13]+'_'+jour_heure[14:16]+'_'+jour_heure[17:19]  # récupération de l'heure 
        
        # création de la nouvelle table pour le cache : 
        c.execute("CREATE TABLE IF NOT EXISTS 'cache' ('nomGraphe' TEXT,'Date_creation' TEXT,'Heure_creation' TEXT,'URL' TEXT,'ident' INTEGER)")
        
        # On recherche si le graphe existe déjà dans la base de données : 
        c.execute("SELECT * FROM 'cache'")
        r = c.fetchall()  # on récupère toutes les données 
        incr = len(r)   # nombre d'éléments dans la table --> permet de mettre une clé primaire 
        
        # on définit les date et heure à partir desquelles on veut que les graphes soient actualisés : 
        date_min = date_ouverture[0:4]+'_'+date_ouverture[5:7]+'_'+date_ouverture[8:10]
        heure_min = date_ouverture[11:13]+'_'+date_ouverture[14:16]+'_'+date_ouverture[17:19] 
        
        fichier = ''
        
        for a in r : 
            if a[0] == graphique and dateSuperieure(a[1],date_min) and heureSuperieure(a[2],heure_min):
                fichier = a[3]   # on a récupéré le fichier depuis table_cache
                
        if fichier == '' :   # le fichier n'a pas été trouvé dans la base de données, on le créé  
          # génération des courbes dans un fichier PNG, on récupèrera la date et l'heure pour faire la requête sur la table de cache par la suite : 
          fichier = 'courbes/concentration_'+ graphique +'_'+ str(jour)+'_'+str(heure)+'.png' # ajout de la date et l'heure de modif dans le nom  
                
          # on ne sauvegarde la figure que si la requête dans la table ne fonctionne pas : 
          plt.savefig('client/{}'.format(fichier))
          plt.close()
          
          # on ajoute le nom du fichier dans la table de cache : 
          # (dans la bdd on met le nom de la station pour laquelle on trace le graphe, le jour et l'heure)
          c.execute("INSERT INTO 'cache' VALUES (?,?,?,?,?)",(graphique,jour,heure,fichier,incr+1))
          conn.commit()   # enregistre les changements dans la base de données 
        
        # on affiche le graphe sous la carte : 
        #html = '<img src="/{}?{}" alt="ponctualite {}" width="100%">'.format(fichier,self.date_time_string(),self.path)
        body = json.dumps({
                'title': 'Concentration en polluants, station '+graphique, \
                'img': '/'+fichier \
                 });
        # on envoie
        headers = [('Content-Type','application/json')];
        self.send(body,headers)
        
        c.execute("SELECT * FROM 'cache'")
        



##################################################################################################
        
        
        
  #
  # On renvoie le graphe prenant en compte les sélections réalisées par l'utilisateur : 
  #
  def send_selectpol(self):    

    conn = sqlite3.connect('bdd_projetB.db')  # MODIF 
    c = conn.cursor()
    
    if len(self.path_info) <= 1 or self.path_info[1] == '' :
        
        # pour l'instant on laisse comme ça le truc par défaut, à modifier 
        
        stations = [("Rhône Alpes","blue"), ("Auvergne","green"), ("Auvergne-Rhône Alpes","cyan"), ('Bourgogne',"red"), 
                   ('Franche Comté','orange'), ('Bourgogne-Franche Comté','olive') ]
        graphique = 'stations'
    else:
        graphique = self.path_info[1]   # récupère le nom de la station sélectionnée 
        # On teste que la région demandée existe bien
        c.execute("SELECT DISTINCT nom_station FROM 'moyennes-journalieres'")  # MODIF 
        reg = c.fetchall()
        if (self.path_info[1],) in reg:   # Rq: reg est une liste de tuples
          stations = [(self.path_info[1],"blue")]     # MODIF
        else:
            print ('Erreur nom')
            self.send_error(404)    # Station non trouvée -> erreur 404
            return None

    
    # configuration du tracé
    fig1 = plt.figure(figsize=(18,6))
    ax = fig1.add_subplot(111)
    ax.grid(which='major', color='#888888', linestyle='-')
    ax.grid(which='minor',axis='x', color='#888888', linestyle=':')
    ax.xaxis.set_major_locator(pltd.YearLocator())
    ax.xaxis.set_minor_locator(pltd.MonthLocator())
    ax.xaxis.set_minor_locator(pltd.DayLocator())
    ax.xaxis.set_major_formatter(pltd.DateFormatter('%B %Y'))
    ax.xaxis.set_tick_params(labelsize=10)
    ax.xaxis.set_label_text("Date")
    ax.yaxis.set_label_text("Concentration en polluant")  # MODIF 

    # boucle sur les stations (on cherche à afficher la concentration de polluant sur une année pour une station donnée)
    
    for l in (stations) :
         
        c.execute("SELECT * FROM 'moyennes-journalieres' WHERE nom_station=? ORDER BY date_debut",l[:1]) #ou (l[0],) # ajouter ? GROUP BY nom_poll 
        r = c.fetchall()
        print(r)
        
        # MODIF : 
        # création des listes de points pour tracer le graphe : 
        # on va superposer plusieurs courbes sur le graphe en fonction du polluant représenté : 
        
        c.execute("SELECT DISTINCT(nom_poll) FROM 'moyennes-journalieres' WHERE nom_station = ?",l[:1])
        polluants = c.fetchall()
        
        
        # polluants du bouton html : 
        pol = ["monoxyde de carbone","monoxyde d'azote","dioxyde d'azote","ozone","benzène","particules PM10","particules PM2,5","dioxyde de souffre"]
        
        
        ########################### fonction aux : 
        
        def pol_valide(possibles,p):
            for i in range(len(possibles)):
                if possibles[i][0] == p:
                    return(True)
            return(False)
            

        # polluants sélectionnés : 
        pol_select = []
        for i in range(2,10):
            if self.path_info[i] == 'true' :     # il faut vérifier que le polluant est bien mesuré dans la station sélectionnée 
                pol_select.append(pol[i-2])   # on ajoute le polluant de la liste déroulante sélectionné 
        
        
        # on ne va calculer les valeurs que pour ces polluants : 
        x = [[] for i in range(len(pol_select))]   # dates 
        y = [[] for i in range(len(pol_select))]   # valeurs
        chgmt_mois = False    ### COMENTAIRE 
        
        
        
        ################ Fonctions auxillaires ##########################
        def dateSuperieure(d1,d2) :
          if d1[0:4] >= d2[0:4] and d1[5:7] >= d2[5:7] and d1[8:10] >= d2[8:10]:
            return(True)
          return(False)

        def heureSuperieure(h1,h2):
          if h1[0:2] >= h2[0:2] and h1[3:5] >= h2[3:5] and h1[6:8] >= h2[6:8]:
            return(True)
          return(False)
          
        ####################################################################
        #polluant = r[0][9]   # premier polluant 
        """
        m = 0
        i = 0 
        color = ['blue','green','red','orange','purple','pink','black','yellow']
        for a in r : 
          if a[9] in pol_select : 
            ### recherche indice 
            indice = 0 
            for m in range(len(pol_select)):
              if pol_select[m] == a[9]:
                indice = m 
            if not a[15] == '' and not a[12] == '' :
              #x[indice].append(dt.date(int(a[15][:4]),int(a[15][5:7]),int(a[15][8:10])))
              x[indice].append(i)
              y[indice].append(float(a[12]))
              #dt.date(date[0],date[1],j)
              i +=1
            #x[m] = [pltd.date2num(dt.date(int(a[15][:4]),int(a[15][5:7]),1)) for a in r if not a[15] == '']
            #y[m] = [float(a[12]) for a in r if not a[12] == '']
        print(x,y)
          
        for m in range(len(pol_select)):
          plt.plot(x[m],y[m],color[m],linewidth=1, linestyle='-', marker='o', color = color[m], label=pol_select[m])
        """
        
        
        for a in r :    
         
          date = (int(a[15][:4]),int(a[15][5:7]),int(a[15][8:10]))
          i = 0 
          j = 0 
          date_f = (int(a[16][:4]),int(a[16][5:7]),int(a[16][8:10])) # date de fin  
          #while date != date_f : # on ajoute tous les jours entre ces deux dates 
          for k in range(int(a[16][8:10])-int(a[15][8:10])) :   # revoir quel est le problème    
            if (date[1]>0 and date[1]<13) and (date[2]>0 and date[2]<31):
              if date[1] == date_f[1] and a[12] !=None:  # pas de changement de mois 
                #x.append(pltd.date2num(dt.date(date[0],date[1],1)))  # année, mois, jour
                p = a[9]
                indice = 0 
                for m in range(len(pol_select)):
                  if pol_select[m] == p:
                    indice = m
                x[indice].append(dt.date(date[0],date[1],date[2]+i))
                y[indice].append(float(a[12]))
                i +=1 
                date = (date[0],date[1],date[2]+i)
              
              else : # il y a un changement de mois 
              
                if chgmt_mois == True and a[12] !=None:
                  #x.append(pltd.date2num(dt.date(date[0],date[1]+1,1)))
                  p = a[9]
                  indice = 0 
                  for m in range(len(pol_select)):
                    if pol_select[m] == p:
                      indice = m
                  x[indice].append(dt.date(date[0],date[1],j))
                  y[indice].append(float(a[12]))
                  date = (date[0],date[1]+1,j)
                  j += 1 
              
                else :  
                  if a[12] !=None: 
                    #x.append(pltd.date2num(dt.date(date[0],date[1],1)))
                    p = a[9]
                    indice = 0 
                    for m in range(len(pol_select)):
                      if pol_select[m] == p:
                        indice = m
                    x[indice].append(dt.date(date[0],date[1],date[2]+i))
                    y[indice].append(float(a[12]))
                  
                  if date[1]//2 == 0 and date[2] == 30 : 
                    chgmt_mois == True 
                  elif date[1]//2 != 0 and date[2] == 31 :
                    chgmt_mois == True 
                  elif date[1] == 2 and date[2] == 28 : 
                    chgmt_mois == True 
                  i +=1 
                  date = (date[0],date[1],date[2]+i)
                  
                  
   
            
            
          """
          # date de début sélectionnée : 
          debut = (int(self.path_info[10][:4]),int(self.path_info[10][5:7]),int(self.path_info[10][8:]))
          # date de fin sélectionnée :
          fin = (int(self.path_info[11][:4]),int(self.path_info[11][5:7]),int(self.path_info[11][8:]))
    
          
          date = date = (int(a[15][:4]),int(a[15][5:7]),int(a[15][8:10]))
          i = 0 
          j = 0 
          date_f = fin    # date de fin  
          
          # on effectue la boucle seulement si la date est comprise entre le début et la fin : 
          # if dateSuperieure(date,debut) == True and dateSuperieure(fin,date) == True : 
              
          
          
          ###### fonction auxiliaire : 
          #delta = dt.date(fin[0],fin[1],fin[2]) - dt.date(debut[0],debut[1],debut[2])
          #nb = delta.days
              
          for k in range(int(a[15][8:10])-int(self.path_info[10][8:])) :   # revoir quel est le problème    
          #while dateSuperieure(date_f,date) == True : 
          #for k in range(nb):
            if dateSuperieure(date,debut) :
              if isinstance(date[1],int) == True and (date[1]>0 and date[1]<13) and (date[2]>0 and date[2]<31):
                if date[1] == date_f[1] and a[12] !=None:  # pas de changement de mois 
                  #x.append(pltd.date2num(dt.date(date[0],date[1],1)))  # année, mois, jour
                  p = a[9]
                  indice = -1
                  for m in range(len(pol_select)):
                    if pol_select[m] == p:
                      indice = m
                  if indice != -1 and (date[2]>0 and date[2]+i <=30):
                    x[indice].append(dt.date(date[0],date[1],date[2]+i))
                    y[indice].append(float(a[12]))
               
                  i +=1 
                  date = (date[0],date[1],date[2]+i)
              
                else : # il y a un changement de mois 
              
                  if chgmt_mois == True and a[12] !=None:
                    #x.append(pltd.date2num(dt.date(date[0],date[1]+1,1)))
                    p = a[9]
                    indice = -1 
                    for m in range(len(pol_select)):
                      if pol_select[m] == p:
                        indice = m
                    if indice != -1 and (date[2]>0 and date[2]+i <=30): 
                      x[indice].append(dt.date(date[0],date[1],j))
                      y[indice].append(float(a[12]))
             
                    date = (date[0],date[1]+1,j)
                    j += 1 
              
                  else :  
                    if a[12] !=None: 
                      #x.append(pltd.date2num(dt.date(date[0],date[1],1)))
                      p = a[9]
                      indice = -1 
                      for m in range(len(pol_select)):
                        if pol_select[m][0] == p:
                          indice = m
                      if indice != -1 and (date[2]>0 and date[2]+i <=30): 
                        x[indice].append(dt.date(date[0],date[1],date[2]+i))
                        y[indice].append(float(a[12]))
                     
                    if date[1]//2 == 0 and date[2] == 30 : 
                      chgmt_mois == True 
                    elif date[1]//2 != 0 and date[2] == 31 :
                      chgmt_mois == True 
                    elif date[1] == 2 and date[2] == 28 : 
                      chgmt_mois == True 
                    i +=1 
                    date = (date[0],date[1],date[2]+i)
            print(x,y)   # visualiser les listes => souvent elles sont vides : pb à résoudre 
            """
                      
            
        # tracé des courbes des polluants sélectionnés sur l'échelle de temps définie plus haut : 
        
        color = ['blue','green','red','orange','purple','pink','black','yellow']
        #col = rd.choice(color)
        
        for m in range(len(pol_select)):
          plt.plot(x[m],y[m],color[m],linewidth=1, linestyle='-', marker='o', color=color[m], label=pol_select[m])
        
        
        # légendes : 
        plt.legend(loc='lower left')  
        plt.title('Concentration de polluants (en micro_g/m^3)',fontsize=16)  # MODIF
      
        
        #### Gestion du cache : 
        
        # les fonctions auxiliaires ont été définies plus haut         
        
        # on commence par renommer les noms des graphes : ajout de la date de création : 
        jour_heure = str(dt.datetime.today())   # de 0 à 9 inclu : la date, puis un espace (à enlever), puis de 10 à 17 inclu, l'heure
        jour = jour_heure[0:4]+'_'+jour_heure[5:7]+'_'+jour_heure[8:10]   # récupération du jour 
        heure = jour_heure[11:13]+'_'+jour_heure[14:16]+'_'+jour_heure[17:19]  # récupération de l'heure 
        
        # création de la nouvelle table pour le cache : 
        c.execute("CREATE TABLE IF NOT EXISTS 'cache' ('nomGraphe' TEXT,'Date_creation' TEXT,'Heure_creation' TEXT,'URL' TEXT,'ident' INTEGER)")
        
        #### ,PRIMARY KEY('ident' AUTOINCREMENT)
        
        # On recherche si le graphe existe déjà dans la base de données : 
        c.execute("SELECT * FROM 'cache'")
        r = c.fetchall()  # on récupère toutes les données 
        incr = len(r)   # nombre d'éléments dans la table --> permet de mettre une clé primaire 
        
        # on définit les date et heure à partir desquelles on veut que les graphes soient actualisés : 
        date_min = date_ouverture[0:4]+'_'+date_ouverture[5:7]+'_'+date_ouverture[8:10]
        heure_min = date_ouverture[11:13]+'_'+date_ouverture[14:16]+'_'+date_ouverture[17:19] 
        
        fichier = ''
        
        for a in r : 
            if a[0] == graphique and dateSuperieure(a[1],date_min) and heureSuperieure(a[2],heure_min):
                fichier = a[3]   # on a récupéré le fichier depuis table_cache
                
        if fichier == '' :   # le fichier n'a pas été trouvé dans la base de données, on le créé  
          # c'est cette ligne qui renvoie le graphe : 
          # génération des courbes dans un fichier PNG, on récupèrera la date et l'heure pour faire la requête sur la table de cache par la suite : 
          fichier = 'courbes/selectpol_'+ graphique +'_'+ str(jour)+'_'+str(heure)+'.png' # ajout de la date et l'heure de modif dans le nom  
                
          # on ne sauvegarde la figure que si la requête dans la table ne fonctionne pas : 
          plt.savefig('client/{}'.format(fichier))
          plt.close()
          
          # on ajoute le nom du fichier dans la table de cache : 
          # (dans la bdd on met le nom de la station pour laquelle on trace le graphe, le jour et l'heure)
          c.execute("INSERT INTO 'cache' VALUES (?,?,?,?,?)",(graphique,jour,heure,fichier,incr+1))
          conn.commit()   # enregistre les changements dans la base de données 
        
        # on affiche le graphe sous la carte : 
        #html = '<img src="/{}?{}" alt="ponctualite {}" width="100%">'.format(fichier,self.date_time_string(),self.path)
        body = json.dumps({
                'title': 'Concentration en polluants, station '+graphique, \
                'img': '/'+fichier \
                 });
        # on envoie
        headers = [('Content-Type','application/json')];
        self.send(body,headers)
        
        c.execute("SELECT * FROM 'cache'")
        #print('contenu_table =',c.fetchall())


##############################################################################


  #
  # On renvoie le graphe des concentrations en polluant par commune par un clique sur un bouton 'commune' : 
  #
  def send_commune(self):    

    conn = sqlite3.connect('bdd_projetB.db')  # MODIF 
    c = conn.cursor()
    
    if len(self.path_info) <= 1 or self.path_info[1] == '' :
        
        # pour l'instant on laisse comme ça le truc par défaut, à modifier 
        
        communes = [("Rhône Alpes","blue"), ("Auvergne","green"), ("Auvergne-Rhône Alpes","cyan"), ('Bourgogne',"red"), 
                   ('Franche Comté','orange'), ('Bourgogne-Franche Comté','olive') ]
        graphique = 'stations'
    else:
        graphique = self.path_info[1]   # récupère le nom de la station sélectionnée 
        # On teste que la région demandée existe bien
        c.execute("SELECT DISTINCT nom_com FROM 'moyennes-journalieres'")  # MODIF 
        reg = c.fetchall()
        if (self.path_info[1],) in reg:   # Rq: reg est une liste de tuples
          communes = [(self.path_info[1],"blue")]     # MODIF
        else:
            print ('Erreur nom')
            self.send_error(404)    # Station non trouvée -> erreur 404
            return None

    
    # configuration du tracé
    fig1 = plt.figure(figsize=(18,6))
    ax = fig1.add_subplot(111)
    ax.grid(which='major', color='#888888', linestyle='-')
    ax.grid(which='minor',axis='x', color='#888888', linestyle=':')
    ax.xaxis.set_major_locator(pltd.YearLocator())
    ax.xaxis.set_minor_locator(pltd.MonthLocator())
    ax.xaxis.set_minor_locator(pltd.DayLocator())
    ax.xaxis.set_major_formatter(pltd.DateFormatter('%B %Y'))
    ax.xaxis.set_tick_params(labelsize=10)
    ax.xaxis.set_label_text("Date")
    ax.yaxis.set_label_text("Concentration en polluant")  # MODIF 

    # boucle sur les stations (on cherche à afficher la concentration de polluant sur une année pour une station donnée)
    for l in (communes) :
         
        c.execute("SELECT SUM(valeur),date_debut,date_fin,nom_poll FROM 'moyennes-journalieres' WHERE nom_com = ? ORDER BY date_debut",l[:1]) #ou (l[0],) # MODIF 
        r = c.fetchall()

        ################ Fonctions auxillaires ##########################
        def dateSuperieure(d1,d2) :
          if d1[0:4] >= d2[0:4] and d1[5:7] >= d2[5:7] and d1[8:10] >= d2[8:10]:
            return(True)
          return(False)

        def heureSuperieure(h1,h2):
          if h1[0:2] >= h2[0:2] and h1[3:5] >= h2[3:5] and h1[6:8] >= h2[6:8]:
            return(True)
          return(False)
        
        
        # MODIF : 
        # création des listes de points pour tracer le graphe : 
        # on va superposer plusieurs courbes sur le graphe en fonction du polluant représenté : 
        
        c.execute("SELECT DISTINCT(nom_poll) FROM 'moyennes-journalieres' WHERE nom_com = ?",l[:1])
        polluants = c.fetchall()
        x = [[] for i in range(len(polluants))]   # dates 
        y = [[] for i in range(len(polluants))]   # valeurs
        chgmt_mois = False
        
        for a in r : 
          #date = pltd.date2num(dt.date(int(a[15][:4]),int(a[15][5:7]),int(a[15][8:]),1))  # date de début des mesures 
          date = (int(a[1][:4]),int(a[1][5:7]),int(a[1][8:10]))
          i = 0 
          j = 0 
          date_f = (int(a[2][:4]),int(a[2][5:7]),int(a[2][8:10])) # date de fin  
          while dateSuperieure(date_f,date) : # on ajoute tous les jours entre ces deux dates 
          #for k in range(int(a[2][8:10])-int(a[1][8:10])) :   # revoir quel est le problème    
            if (date[1]>0 and date[1]<13) and (date[2]>0 and date[2]<31):
              if date[1] == date_f[1] and a[0] !=None:  # pas de changement de mois 
                #x.append(pltd.date2num(dt.date(date[0],date[1],1)))  # année, mois, jour
                p = a[3]
                indice = 0 
                for m in range(len(polluants)):
                  if polluants[m][0] == p:
                    indice = m
                x[indice].append(dt.date(date[0],date[1],date[2]+i))
                y[indice].append(float(a[0]))
                i +=1 
                date = (date[0],date[1],date[2]+i)
              
              else : # il y a un changement de mois 
              
                if chgmt_mois == True and a[0] !=None:
                  #x.append(pltd.date2num(dt.date(date[0],date[1]+1,1)))
                  p = a[3]
                  indice = 0 
                  for m in range(len(polluants)):
                    if polluants[m][0] == p:
                      indice = m
                  x[indice].append(dt.date(date[0],date[1],j))
                  y[indice].append(float(a[0]))
                  date = (date[0],date[1]+1,j)
                  j += 1 
              
                else :  
                  if a[2] !=None: 
                    #x.append(pltd.date2num(dt.date(date[0],date[1],1)))
                    p = a[3]
                    indice = 0 
                    for m in range(len(polluants)):
                      if polluants[m][0] == p:
                        indice = m
                    x[indice].append(dt.date(date[0],date[1],date[2]+i))
                    y[indice].append(float(a[0]))
                  
                  if date[1]//2 == 0 and date[2] == 30 : 
                    chgmt_mois == True 
                  elif date[1]//2 != 0 and date[2] == 31 :
                    chgmt_mois == True 
                  elif date[1] == 2 and date[2] == 28 : 
                    chgmt_mois == True 
                  i +=1 
                  date = (date[0],date[1],date[2]+i)
        print(x,y)            
            
        # tracé des courbes : 
        color = ['blue','green','red','orange','purple','pink','black']
        for m in range(len(polluants)):
          plt.plot(x[m],y[m],color[m],linewidth=1, linestyle='-', marker='o', color=color[m], label=polluants[m][0])
        
        # légendes : 
        plt.legend(loc='lower left')  
        plt.title('Concentration de polluants par commune (en micro_g/m^3)',fontsize=16)  # MODIF
      
        
        #### Gestion du cache : 
        

        # on commence par renommer les noms des graphes : ajout de la date de création : 
        jour_heure = str(dt.datetime.today())   # de 0 à 9 inclu : la date, puis un espace (à enlever), puis de 10 à 17 inclu, l'heure
        jour = jour_heure[0:4]+'_'+jour_heure[5:7]+'_'+jour_heure[8:10]   # récupération du jour 
        heure = jour_heure[11:13]+'_'+jour_heure[14:16]+'_'+jour_heure[17:19]  # récupération de l'heure 
        
        # création de la nouvelle table pour le cache : 
        c.execute("CREATE TABLE IF NOT EXISTS 'cache' ('nomGraphe' TEXT,'Date_creation' TEXT,'Heure_creation' TEXT,'URL' TEXT,'ident' INTEGER)")
        
        #### ,PRIMARY KEY('ident' AUTOINCREMENT)
        
        # On recherche si le graphe existe déjà dans la base de données : 
        c.execute("SELECT * FROM 'cache'")
        r = c.fetchall()  # on récupère toutes les données 
        incr = len(r)   # nombre d'éléments dans la table --> permet de mettre une clé primaire 
        
        # on définit les date et heure à partir desquelles on veut que les graphes soient actualisés : 
        date_min = date_ouverture[0:4]+'_'+date_ouverture[5:7]+'_'+date_ouverture[8:10]
        heure_min = date_ouverture[11:13]+'_'+date_ouverture[14:16]+'_'+date_ouverture[17:19] 
        
        fichier = ''
        
        for a in r : 
            if a[0] == graphique and dateSuperieure(a[1],date_min) and heureSuperieure(a[2],heure_min):
                fichier = a[3]   # on a récupéré le fichier depuis table_cache
                
        if fichier == '' :   # le fichier n'a pas été trouvé dans la base de données, on le créé  
          # c'est cette ligne qui renvoie le graphe : 
          # génération des courbes dans un fichier PNG, on récupèrera la date et l'heure pour faire la requête sur la table de cache par la suite : 
          fichier = 'courbes/commune'+ graphique +'_'+ str(jour)+'_'+str(heure)+'.png' # ajout de la date et l'heure de modif dans le nom  
                
          # on ne sauvegarde la figure que si la requête dans la table ne fonctionne pas : 
          plt.savefig('client/{}'.format(fichier))
          plt.close()
          
          # on ajoute le nom du fichier dans la table de cache : 
          # (dans la bdd on met le nom de la station pour laquelle on trace le graphe, le jour et l'heure)
          c.execute("INSERT INTO 'cache' VALUES (?,?,?,?,?)",(graphique,jour,heure,fichier,incr+1))
          conn.commit()   # enregistre les changements dans la base de données 
        
        # on affiche le graphe sous la carte : 
        #html = '<img src="/{}?{}" alt="ponctualite {}" width="100%">'.format(fichier,self.date_time_string(),self.path)
        body = json.dumps({
                'title': 'Concentration en polluants, station '+graphique, \
                'img': '/'+fichier \
                 });
        # on envoie
        headers = [('Content-Type','application/json')];
        self.send(body,headers)
        
        c.execute("SELECT * FROM 'cache'")
        #print('contenu_table =',c.fetchall())
  
  
  #
  # On envoie les entêtes et le corps fourni
  #
  def send(self,body,headers=[]):

    # on encode la chaine de caractères à envoyer
    encoded = bytes(body, 'UTF-8')

    # on envoie la ligne de statut
    self.send_response(200)

    # on envoie les lignes d'entête et la ligne vide
    [self.send_header(*t) for t in headers]
    self.send_header('Content-Length',int(len(encoded)))
    self.end_headers()

    # on envoie le corps de la réponse
    self.wfile.write(encoded)

 
#
# Instanciation et lancement du serveur
#
httpd = socketserver.TCPServer(("", PORT), RequestHandler)
print ("serveur sur port : {}".format(PORT))
httpd.serve_forever()


