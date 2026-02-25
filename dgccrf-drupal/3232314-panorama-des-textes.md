---
title: "Panorama des textes"
nid: 3232314
type: "page_contenu"
status: 1
langcode: "fr"
created: "2024-12-17"
changed: "2025-07-16"
alias: "/dgccrf/les-fiches-pratiques-et-les-faq/panorama-des-textes"
menu_path: "Les fiches pratiques et les FAQ > Panorama des textes"
source: "dgccrf"
---

# Panorama des textes

angular.module('ods-widgets').controller('QueryController', function($scope, $filter) {
 $scope.$watchGroup(['recherche.text', 'dates.dateDebut', 'dates.dateFin'], function(newValues, oldValues) {
 var query = '';
 var text = newValues[0];
 var dateDebut = newValues[1];
 var dateFin = newValues[2];
 
 if (text) {
 query = text;
 }
 
 if (dateDebut || dateFin) {
 var dateQuery = '';
 if (dateDebut && dateFin) {
 var dateDebutFormatted = $filter('moment')(dateDebut, 'YYYY-MM-DD');
 var dateFinFormatted = $filter('moment')(dateFin, 'YYYY-MM-DD');
 dateQuery = 'date_de_publication >= ' + dateDebutFormatted + ' AND date_de_publication = ' + dateDebutFormatted;
 } else if (dateFin) {
 var dateFinFormatted = $filter('moment')(dateFin, 'YYYY-MM-DD');
 dateQuery = 'date_de_publication 
 
 
 
 
 
 Rechercher dans les textes juridiques...
 
 
 
 
 
 
 
 
 Thématique
 
 
 Sélectionnez une thématique
 
 
 
 
 
 
 Nature juridique
 
 
 Sélectionnez une nature
 
 
 
 
 
 
 
 
 Publié entre lesaisir le date de début de publication
 
 
 
 
 
 et lesaisir le date de fin de publication
 
 
 
 
 
 
 
 
 Réinitialiser 
 
 
 
 
 

 


{{ items.length == 100 ? 'Plus de 100' : items.length }} résultat{{ items.length > 1 ? 's' : '' }} trouvé{{ items.length > 1 ? 's' : '' }}
 
 
 

 
### {{ item.fields.titre_long }}

 

{{ item.fields.texte_complet }}
 
 
 

{{ item.fields.date_de_publication | date:'dd/MM/yyyy' }}

 

{{ item.fields.nature_juridique }}
 

{{ item.fields.publication }}
 
 

 
 
 
 [Consulter le texte]({{ item.fields.lien_hypertexte }})
