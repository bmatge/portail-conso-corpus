---
title: "Rechercher un produit dont la composition a été temporairement modifiée"
nid: 104638
type: "article_espace"
status: 1
langcode: "fr"
created: "2022-04-04"
changed: "2025-06-27"
alias: "/dgccrf/rechercher-produit-composition-temporairement-modifiee"
taxonomy: ["Information sur les produits", "Alimentation, restauration", "Fiche Particuliers", "Fiches Professionnels"]
source: "dgccrf"
---

# Rechercher un produit dont la composition a été temporairement modifiée

La crise en Ukraine et en Russie affecte l’approvisionnement de l'industrie alimentaire pour la production de certaines denrées. Des dérogations d’étiquetage sur la composition sont possibles afin de permettre la poursuite de la production à condition que cela n’affecte pas la sécurité des consommateurs, notamment en cas d’allergie.
 


 Vous pouvez utiliser le moteur de recherche ci-dessous pour trouver votre produit (par nom, marque, numéro EAN figurant sous le code barre), ou [consulter les informations sur la mesure](/dgccrf/modifications-temporaires-de-recette-et-derogations-detiquetage-liees-la-crise-en-ukraine).
 

 
 
 

 
 
 
 
 
 Catégorie de produit
 
 
 Toutes les catégories
 
 
 
 

 
 
 Impact allergènes
 
 
 Tous les produits
 
 
 
 

 
 **
 Réinitialiser les filtres
 
 
 
 
 
 


 {{ ctx.dataset.metas.records_count || 0 }}** produit(s) trouvé(s)
 
 
 
 
 
 

 
 

 
 

 
### {{ item.fields.denomination_du_produit }}


 
 

 

**Marque :** {{ item.fields.marque }}

 
 

{{ item.fields.impact_allergenes }}
 
 

Conditionnement : {{ item.fields.conditionnement }}

 Catégorie : {{ item.fields.categorie_du_produit_rayon }}

 Code-barres : {{ item.fields.code_barre_ean_gtin }}

 Date de dépôt : {{ item.fields.datedepot | date:'dd/MM/yyyy' }}

 Information des consommateurs : {{ item.fields.modalites_d_information_des_consommateurs }}
 

**Nature du décalage : {{ item.fields.nature_du_decalage_entre_le_produit_et_son_etiquetage }}**
 




 
 


 
- 
 

{{ item.fields.categorie_du_produit_rayon }}
 
 

 

 
 

 
 
 

 
 

 
 [
 Voir les données complètes
 ](https://data.economie.gouv.fr/explore/dataset/demarches-simplifiees-etikraine)
