---
title: "Tableau de bord RappelConso"
nid: 3234239
type: "page_contenu"
status: 1
langcode: "fr"
created: "2025-04-01"
changed: "2025-04-04"
alias: "/dgccrf/laction-de-la-dgccrf/les-alertes-et-rappels-de-produits/tableau-de-bord-rappelconso"
menu_path: "L'action de la DGCCRF > Les alertes et rappels de produits > Tableau de bord RappelConso"
source: "dgccrf"
---

# Tableau de bord RappelConso

{{rappelconsoannee.parameters['refine.categorie_de_produit']=rappelconsomois.parameters['refine.categorie_de_produit']=rappelconso.parameters['refine.categorie_de_produit'] ; ''}}

 
 {{rappelconsoannee.parameters['refine.sous_categorie_de_produit']=rappelconsomois.parameters['refine.sous_categorie_de_produit']=rappelconso.parameters['refine.sous_categorie_de_produit'] ; ''}}

 
 
 
 
 {{jourdubulletin = ((dates.selecteddate | momentadd:'hours':1) || now) ; ''}} {{anneedubulletin = (((jourdubulletin | moment:'YYYY') + '-01-01') | moment:'YYYY-MM-DD') ; '' }} {{moisdubulletin = ((jourdubulletin | moment:'YYYY') + '-' + (jourdubulletin | moment:'MM') + '-01') ; '' }}

 
 {{rappelconso.parameters['q'] = 'date_de_publication = ' + anneedubulletin + ' AND date_de_publication = ' + moisdubulletin + ' AND date_de_publication > ' + (jourdubulletin | moment:' YYYY-MM-DD') ; '' }}
 
 
 
 
 Données en date du {{ (dates.selecteddate | moment:'DD/MM/YYYY') || (now | moment:'DD/MM/YYYY')}}
 Vous pouvez également sélectionner une autre date
 *
 
 
 
 
 
 
 
 
 
## Filtres

 
 
 
 Catégorie du produit 
 
 Sélectionner une catégorie
 {{c.name}}
 
 
 
 
 
 Sous-catégorie du produit 
 
 Sélectionner une sous-catégorie
 {{c.name}}
 
 
 
 
 
 0 || rappelconso.parameters['refine.sous_categorie_de_produit'].length>0">
 

 
 0" ng-click="rappelconso.parameters['refine.categorie_de_produit']=[]" title="Supprimer le filtre sélectionné">
 Catégorie sélectionnée :
 {{rappelconso.parameters['refine.categorie_de_produit']}} *
 
 0" ng-click="rappelconso.parameters['refine.sous_categorie_de_produit']=[]" title="Supprimer le filtre sélectionné">
 Catégorie sélectionnée :
 {{rappelconso.parameters['refine.sous_categorie_de_produit']}} **
 
 


 
 
 
 
 
 
 
 
## Nombre de rappels


 
 

 
 
 
 
 
### {{rappelconso.nhits | number:0}}

 

Sur toute la période (depuis Mars 2021)
 
 
 
 

 
 
 
 
 
### {{rappelconsoannee.nhits | number:0}}

 

Sur l'année {{dates.selecteddate | moment:'YYYY'}}
 
 
 
 

 
 
 
 
 
### {{rappelconsomois.nhits | number:0}}

 

Sur le mois {{dates.selecteddate | moment:'MM/YYYY'}}
 
 
 
 
 
 
 
 
## Graphiques


 
 
 
 
#### Répartition par catégorie de produits

 
 
 
 
 
 
 
 
 
 
#### Famille de produits avec le plus de rappels

 
 
 
 
 
 
 
 
 
 
#### Nature juridique du rappel

 
 
 
 
 
 
 
 
 
 
#### Modalités de compensation

 
 
 
 
 
 
 
 
 
 
 
 [
 Consultez les données
 ](https://data.economie.gouv.fr/explore/dataset/{{allsignals.dataset.datasetid}}/)

select { 
 background-color: #eee !important;}
.ods-box {
 border:unset;
 box-shadow: 0 0 0 1px var(--border-default-grey);
 margin:0
 
}
.filters-summary {
 display: flex;
 flex-direction: column;
 gap: 10px;
}
@media screen and (max-width:1024px) {
 .d-block-tab {
 display:block
 }
 .d-block-tab > * { width : 100%; max-width:100%}
 .tab-mt { margin-top:20px}
}
@media screen and (max-width:600px) {
 .d-block-mob {
 display:block
 }
}
