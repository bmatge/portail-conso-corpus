---
title: "Le tableau de bord de SignalConso"
nid: 3234169
type: "page_contenu"
status: 1
langcode: "fr"
created: "2025-03-27"
changed: "2025-04-01"
alias: "/dgccrf/laction-de-la-dgccrf/le-tableau-de-bord-de-signalconso"
menu_path: "L'action de la DGCCRF > Le tableau de bord de SignalConso"
source: "dgccrf"
---

# Le tableau de bord de SignalConso

{{jourdubulletin = ((dates.selecteddate | momentadd:'hours':1) || now) ; ''}} {{anneedubulletin = (((jourdubulletin | moment:'YYYY') + '-01-01') | moment:'YYYY-MM-DD') ; '' }} {{moisdubulletin = ((jourdubulletin | moment:'YYYY') + '-' + (jourdubulletin | moment:'MM') + '-01') ; '' }} {{semainedubulletin = (jourdubulletin | momentadd:'days':-((jourdubulletin | moment:'d')==0 ? 6 : ((jourdubulletin | moment:'d')-1)) | moment:'YYYY-MM-DD') ; '' }}

 
 {{allsignals.parameters['q']=(variables.selectedperiod.length==0 ? 'creationdate = ' + anneedubulletin + ' AND creationdate = ' + moisdubulletin + ' AND creationdate = ' + semainedubulletin + ' AND creationdate 
 {{listecollterr.parameters['refine.reg_code'] = allsignals.parameters['refine.reg_code'] = (variables.strate=='region' ? variables.selectid[0] : undefined) ; ''}} {{listecollterr.parameters['refine.dep_code'] = allsignals.parameters['refine.dep_code'] = (variables.strate=='departement' ? variables.selectid[0] : undefined) ; ''}}

 
 
 
 
 
 
Données en date du {{ (dates.selecteddate | moment:'DD/MM/YYYY') || (now | moment:'DD/MM/YYYY')}}
 Vous pouvez également sélectionner une autre date
 *
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 Par région
 Par département
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 

 
 0" >
 Période :
 {{variables.selectedperiod[0].libelle}} *
 
 
 Période :
 Depuis le début de la collecte
 

 0" >
 
 Région sélectionnée : {{items[0].fields.reg_name}} **
 
 
 Département sélectionné : {{variables.selectid[0]}} - {{items[0].fields.dep_name}} **
 
 
 
 
 
 
 
 
 
 
 
 
 Pour afficher la carte correctement, merci de changer de navigateur (Microsoft Edge, Mozilla Firefx, Safari ou Google Chrome).
 
 {{ variables.svgpathsregions = pathsregions ; "" }} {{ variables.svgpathswithdefault = [{"fields":{"id":"","data_name":"Toute la France"} }].concat(variables.svgpathsregions) ; '' }} 

 
 
 
 
 
 
 

Sélectionner une région pour filtrer les indicateurs et les graphiques.
 Afficher drom tom
 0">
 
 
 
 
 [
 


 ](#)
 
 
 
 
 
 
 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 

 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 
 

 
 
 
 
 
 
 
 
 
 
 Pour afficher la carte correctement, merci de changer de navigateur (Microsoft Edge, Mozilla Firefx, Safari ou Google Chrome).

 
 {{ variables.svgpathsdepartements = pathsdepartements ; "" }} {{ variables.svgpathswithdefault = [{"fields":{"id":"","data_name":"Toute la France"} }].concat(variables.svgpathsdepartements) ; '' }} 

 
 
 
 

 
 
 

Sélectionner un département pour filtrer les indicateurs et les graphiques.
 0">
 
 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 

 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 
 
 
 [
 


 {{ path.fields.data_name }}
 ](#)
 
 
 
 
 
 
 
 

 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
 
### {{results[0].nb_signalements | number:0}}

 

Nombre de signalements
 
 
 
 
 
 
 
 
 
 
### {{ (results[0].nb_transmis/results[0].nb_signalements*100 || 0) | number:2}}%

 

{{ '(' + (results[0].nb_transmis | number:0) + ' signalements transmis sur un total de ' + (results[0].nb_signalements | number:0) + ' signalements)'}}
Part de signalements transmis
 
 
 
 
 
 
 
 
 
 
### {{ (results[0].nb_lus/results[0].nb_transmis*100 || 0) | number:2}}%

 

{{ '(' + (results[0].nb_lus | number:0) + ' signalements lus sur un total de ' + (results[0].nb_transmis | number:0) + ' signalements transmis)'}}
Part des signalements transmis qui ont été lus
 
 
 
 
 
 
 
 
 
 
### {{ (results[0].nb_reponses/results[0].nb_lus*100 || 0) | number:2}}%

 

{{ '(' + (results[0].nb_reponses | number:0) + ' signalements ayant reçu une réponse sur un total de ' + (results[0].nb_lus | number:0) + ' signalements lus)'}}
Part des signalements lus qui ont reçu une réponse
 
 
 
 
 
 
 
 
 
 
 
 
 
### Répartition par catégories

 
 
 
 
 
 
 
 
 
 
### Mots-clés les plus populaires

 
 
 
 
 
 
 
 
 
 
 
 [
 Consultez les données
 ](https://data.economie.gouv.fr/explore/dataset/{{allsignals.dataset.datasetid}}/)

.eco-page-top {margin-bottom: 0rem !important;}

.filters-summary {
 display: flex;
 flex-direction: column;
 gap: 10px;
}
.ods-box {
 border:unset;
 box-shadow: 0 0 0 1px var(--border-default-grey);
 margin:0

}
/* Button Group Switch
========================================================================== */

.switch {
 display: inline-block;
 margin-bottom: 0;
 margin-left: 0.5rem;
}

.switch-button {
 /* background and border when in "off" state */
 background-color: #000091;
 border: 2px solid white;
 display: grid;
 grid-template-columns: 1fr 1fr;
 border-radius: 6px;
 color: #FFFFFF;
 position: relative;
 cursor: pointer;
 outline: 0;
 user-select: none;
 border: 1px solid #808080;
 margin-bottom: 10px;
}
.switch-button .switch-button-left {
 /* text color when in "off" state */
 color: #fff;
}
.switch-input:checked + .switch-button .switch-button-left {
 /* text color when in "off" state */
 color: #000091;
}

.switch-input {
 display: none;
}

.switch-button span {
 font-size: 1rem;
 padding: 0.2rem 0.7rem;
 text-align: center;
 z-index: 2;
 color: #000091;
 transition: color 0.2s;
}

.switch-button::before {
 content: "";
 position: absolute;
 background-color: white;
 box-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
 border-radius: 4px;
 top: 0;
 left: 50%;
 height: 100%;
 width: 50%;
 z-index: 1;
 transition: left 0.3s cubic-bezier(0.175, 0.885, 0.32, 1), padding 0.2s ease, margin 0.2s ease;
}

.switch-button:hover::before {
 will-change: padding;
}

.switch-button:active::before {
 padding-right: 0.4rem;
}

/* "On" state
========================== */
.switch-input:checked + .switch-button {
 /* background and border when in "on" state */
}

.switch-input:checked + .switch-button .switch-button-right {
 /* text color when in "on" state */
 color: #fff;
 background: #000091
}

.switch-input:checked + .switch-button::before {
 left: 0%;

}

.switch-input:checked + .switch-button:active::before {
 margin-left: -0.4rem;
}

/* Checkbox in disabled state
========================== */
.switch-input[type=checkbox]:disabled + .switch-button {
 opacity: 0.6;
 cursor: not-allowed;
}

/**
* License: MIT License
* Generated on 26 May 2021
* Author: Fpassaniti for Opendatasoft
* Version: 0.1
* Description: ods-chart CUSTOM CSS LIBRARY. Go to http://codelibrary.opendatasoft.com/widget-tricks/ods-chart-css/ for more information (doc & examples).
*/
.extralarge-y-values .highcharts-yaxis-labels text, .large-y-values .highcharts-yaxis-labels text {
 transform: translate(0, 4px);
}

.hide-chart-legend .highcharts-legend-item span, .hide-chart-series .highcharts-series path.highcharts-graph, .hide-chart-series .highcharts-series rect, .hide-data-values .highcharts-data-label tspan, .hide-tooltip-text .highcharts-tooltip .highcharts-tooltip-container, .hide-tooltip-text .ods-highcharts__tooltip span, .hide-x-axisline .highcharts-axis.highcharts-xaxis path.highcharts-axis-line, .hide-x-axisline-ticks .highcharts-axis.highcharts-xaxis path.highcharts-tick, .hide-x-gridline .highcharts-xaxis-grid path.highcharts-grid-line, .hide-x-legend .highcharts-xaxis tspan, .hide-x-values .highcharts-xaxis-labels span, .hide-x-values .highcharts-xaxis-labels text, .hide-y-axisline .highcharts-axis.highcharts-yaxis path.highcharts-axis-line, .hide-y-gridline .highcharts-yaxis-grid path.highcharts-grid-line, .hide-y-legend .highcharts-yaxis tspan, .hide-y-values .highcharts-yaxis-labels span, .hide-y-values .highcharts-yaxis-labels text, .name-tooltip-value .ods-highcharts__tooltip b {
 display: none !important;
}

.highcharts-axis tspan, .highcharts-data-label tspan, .highcharts-label span, .highcharts-legend-item span, .highcharts-xaxis-labels text, .highcharts-yaxis-labels text {
 font-family: Gotham-book, Arial, sans-serif !important;
}

.name-tooltip-value .ods-highcharts__tooltip b, .small-chart-legend .highcharts-legend-item span, .small-data-values .highcharts-data-label tspan, .small-tooltip-text .highcharts-tooltip .highcharts-tooltip-container, .small-tooltip-text .ods-highcharts__tooltip span, .small-x-legend .highcharts-xaxis tspan, .small-x-values .highcharts-xaxis-labels span, .small-x-values .highcharts-xaxis-labels text, .small-y-legend .highcharts-yaxis tspan, .small-y-values .highcharts-yaxis-labels span, .small-y-values .highcharts-yaxis-labels text {
 font-size: 12px !important;
}

.medium-chart-legend .highcharts-legend-item span, .medium-data-values .highcharts-data-label tspan, .medium-tooltip-text .highcharts-tooltip .highcharts-tooltip-container, .medium-tooltip-text .ods-highcharts__tooltip span, .medium-x-legend .highcharts-xaxis tspan, .medium-x-values .highcharts-xaxis-labels span, .medium-x-values .highcharts-xaxis-labels text, .medium-y-legend .highcharts-yaxis tspan, .medium-y-values .highcharts-yaxis-labels span, .medium-y-values .highcharts-yaxis-labels text, .name-tooltip-value .ods-highcharts__tooltip b {
 font-size: 14px !important;
}

.large-chart-legend .highcharts-legend-item span, .large-data-values .highcharts-data-label tspan, .large-tooltip-text .highcharts-tooltip .highcharts-tooltip-container, .large-tooltip-text .ods-highcharts__tooltip span, .large-x-legend .highcharts-xaxis tspan, .large-x-values .highcharts-xaxis-labels span, .large-x-values .highcharts-xaxis-labels text, .large-y-legend .highcharts-yaxis tspan, .large-y-values .highcharts-yaxis-labels span, .large-y-values .highcharts-yaxis-labels text, .name-tooltip-value .ods-highcharts__tooltip b {
}

.extralarge-chart-legend .highcharts-legend-item span, .extralarge-data-values .highcharts-data-label tspan, .extralarge-tooltip-text .highcharts-tooltip .highcharts-tooltip-container, .extralarge-tooltip-text .ods-highcharts__tooltip span, .extralarge-x-legend .highcharts-xaxis tspan, .extralarge-x-values .highcharts-xaxis-labels span, .extralarge-x-values .highcharts-xaxis-labels text, .extralarge-y-legend .highcharts-yaxis tspan, .extralarge-y-values .highcharts-yaxis-labels span, .extralarge-y-values .highcharts-yaxis-labels text, .name-tooltip-value .ods-highcharts__tooltip b {
 font-size: 18px !important;
}

.light-chart-legend .highcharts-legend-item span, .light-data-values .highcharts-data-label tspan, .light-tooltip-text .highcharts-tooltip .highcharts-tooltip-container, .light-tooltip-text .ods-highcharts__tooltip span, .light-x-legend .highcharts-xaxis tspan, .light-x-values .highcharts-xaxis-labels span, .light-x-values .highcharts-xaxis-labels text, .light-y-legend .highcharts-yaxis tspan, .light-y-values .highcharts-yaxis-labels span, .light-y-values .highcharts-yaxis-labels text, .name-tooltip-value .ods-highcharts__tooltip b {
 font-weight: 100 !important;
}

.name-tooltip-value .ods-highcharts__tooltip b, .normal-chart-legend .highcharts-legend-item span, .normal-data-values .highcharts-data-label tspan, .normal-tooltip-text .highcharts-tooltip .highcharts-tooltip-container, .normal-tooltip-text .ods-highcharts__tooltip span, .normal-x-legend .highcharts-xaxis tspan, .normal-x-values .highcharts-xaxis-labels span, .normal-x-values .highcharts-xaxis-labels text, .normal-y-legend .highcharts-yaxis tspan, .normal-y-values .highcharts-yaxis-labels span, .normal-y-values .highcharts-yaxis-labels text {
 font-weight: 400 !important;
}

.bold-chart-legend .highcharts-legend-item span, .bold-data-values .highcharts-data-label tspan, .bold-tooltip-text .highcharts-tooltip .highcharts-tooltip-container, .bold-tooltip-text .ods-highcharts__tooltip span, .bold-x-legend .highcharts-xaxis tspan, .bold-x-values .highcharts-xaxis-labels span, .bold-x-values .highcharts-xaxis-labels text, .bold-y-legend .highcharts-yaxis tspan, .bold-y-values .highcharts-yaxis-labels span, .bold-y-values .highcharts-yaxis-labels text, .name-tooltip-value .ods-highcharts__tooltip b {
 font-weight: 600 !important;
}

.lightgrey-chart-legend .highcharts-legend-item span, .lightgrey-data-values .highcharts-data-label tspan, .lightgrey-tooltip-text .highcharts-tooltip .highcharts-tooltip-container, .lightgrey-tooltip-text .ods-highcharts__tooltip span, .lightgrey-x-legend .highcharts-xaxis tspan, .lightgrey-x-values .highcharts-xaxis-labels span, .lightgrey-x-values .highcharts-xaxis-labels text, .lightgrey-y-legend .highcharts-yaxis tspan, .lightgrey-y-values .highcharts-yaxis-labels span, .lightgrey-y-values .highcharts-yaxis-labels text, .name-tooltip-value .ods-highcharts__tooltip b {
 fill: #565656 !important;
 color: #565656 !important;
}

.darkgrey-chart-legend .highcharts-legend-item span, .darkgrey-data-values .highcharts-data-label tspan, .darkgrey-tooltip-text .highcharts-tooltip .highcharts-tooltip-container, .darkgrey-tooltip-text .ods-highcharts__tooltip span, .darkgrey-x-legend .highcharts-xaxis tspan, .darkgrey-x-values .highcharts-xaxis-labels span, .darkgrey-x-values .highcharts-xaxis-labels text, .darkgrey-y-legend .highcharts-yaxis tspan, .darkgrey-y-values .highcharts-yaxis-labels span, .darkgrey-y-values .highcharts-yaxis-labels text, .name-tooltip-value .ods-highcharts__tooltip b {
 fill: #333 !important;
 color: #333 !important;
}

.black-chart-legend .highcharts-legend-item span, .black-data-values .highcharts-data-label tspan, .black-tooltip-text .highcharts-tooltip .highcharts-tooltip-container, .black-tooltip-text .ods-highcharts__tooltip span, .black-x-legend .highcharts-xaxis tspan, .black-x-values .highcharts-xaxis-labels span, .black-x-values .highcharts-xaxis-labels text, .black-y-legend .highcharts-yaxis tspan, .black-y-values .highcharts-yaxis-labels span, .black-y-values .highcharts-yaxis-labels text, .name-tooltip-value .ods-highcharts__tooltip b {
 fill: #000 !important;
 color: #000 !important;
}

.small-chart-legend-dash .highcharts-legend-item path, .small-chart-series .highcharts-series path.highcharts-graph, .small-chart-series .highcharts-series rect, .small-x-axisline .highcharts-axis.highcharts-xaxis path.highcharts-axis-line, .small-x-axisline-ticks .highcharts-axis.highcharts-xaxis path.highcharts-tick, .small-x-gridline .highcharts-xaxis-grid path.highcharts-grid-line, .small-y-axisline .highcharts-axis.highcharts-yaxis path.highcharts-axis-line, .small-y-gridline .highcharts-yaxis-grid path.highcharts-grid-line {
 stroke-width: 0.8px !important;
}

.medium-chart-legend-dash .highcharts-legend-item path, .medium-chart-series .highcharts-series path.highcharts-graph, .medium-chart-series .highcharts-series rect, .medium-x-axisline .highcharts-axis.highcharts-xaxis path.highcharts-axis-line, .medium-x-axisline-ticks .highcharts-axis.highcharts-xaxis path.highcharts-tick, .medium-x-gridline .highcharts-xaxis-grid path.highcharts-grid-line, .medium-y-axisline .highcharts-axis.highcharts-yaxis path.highcharts-axis-line, .medium-y-gridline .highcharts-yaxis-grid path.highcharts-grid-line {
 stroke-width: 1.5px !important;
}

.large-chart-legend-dash .highcharts-legend-item path, .large-chart-series .highcharts-series path.highcharts-graph, .large-chart-series .highcharts-series rect, .large-x-axisline .highcharts-axis.highcharts-xaxis path.highcharts-axis-line, .large-x-axisline-ticks .highcharts-axis.highcharts-xaxis path.highcharts-tick, .large-x-gridline .highcharts-xaxis-grid path.highcharts-grid-line, .large-y-axisline .highcharts-axis.highcharts-yaxis path.highcharts-axis-line, .large-y-gridline .highcharts-yaxis-grid path.highcharts-grid-line {
 stroke-width: 3px !important;
}

.extralarge-chart-legend-dash .highcharts-legend-item path, .extralarge-chart-series .highcharts-series path.highcharts-graph, .extralarge-chart-series .highcharts-series rect, .extralarge-x-axisline .highcharts-axis.highcharts-xaxis path.highcharts-axis-line, .extralarge-x-axisline-ticks .highcharts-axis.highcharts-xaxis path.highcharts-tick, .extralarge-x-gridline .highcharts-xaxis-grid path.highcharts-grid-line, .extralarge-y-axisline .highcharts-axis.highcharts-yaxis path.highcharts-axis-line, .extralarge-y-gridline .highcharts-yaxis-grid path.highcharts-grid-line {
 stroke-width: 5px !important;
}

.lightgrey-chart-series .highcharts-series path.highcharts-graph, .lightgrey-chart-series .highcharts-series rect, .lightgrey-x-axisline .highcharts-axis.highcharts-xaxis path.highcharts-axis-line, .lightgrey-x-axisline-ticks .highcharts-axis.highcharts-xaxis path.highcharts-tick, .lightgrey-x-gridline .highcharts-xaxis-grid path.highcharts-grid-line, .lightgrey-y-axisline .highcharts-axis.highcharts-yaxis path.highcharts-axis-line, .lightgrey-y-gridline .highcharts-yaxis-grid path.highcharts-grid-line {
 stroke: #565656 !important;
}

.lightgrey-chart-legend-dash .highcharts-legend-item path {
 stroke-width: #565656 !important;
}

.darkgrey-chart-series .highcharts-series path.highcharts-graph, .darkgrey-chart-series .highcharts-series rect, .darkgrey-x-axisline .highcharts-axis.highcharts-xaxis path.highcharts-axis-line, .darkgrey-x-axisline-ticks .highcharts-axis.highcharts-xaxis path.highcharts-tick, .darkgrey-x-gridline .highcharts-xaxis-grid path.highcharts-grid-line, .darkgrey-y-axisline .highcharts-axis.highcharts-yaxis path.highcharts-axis-line, .darkgrey-y-gridline .highcharts-yaxis-grid path.highcharts-grid-line {
 stroke: #333 !important;
}

.darkgrey-chart-legend-dash .highcharts-legend-item path {
 stroke-width: #333 !important;
}

.black-chart-series .highcharts-series path.highcharts-graph, .black-chart-series .highcharts-series rect, .black-x-axisline .highcharts-axis.highcharts-xaxis path.highcharts-axis-line, .black-x-axisline-ticks .highcharts-axis.highcharts-xaxis path.highcharts-tick, .black-x-gridline .highcharts-xaxis-grid path.highcharts-grid-line, .black-y-axisline .highcharts-axis.highcharts-yaxis path.highcharts-axis-line, .black-y-gridline .highcharts-yaxis-grid path.highcharts-grid-line {
 stroke: #000 !important;
}

.black-chart-legend-dash .highcharts-legend-item path {
 stroke-width: #000 !important;
}

.hide-chart-legend-dash .highcharts-legend-item path {
 stroke-width: none !important;
}

.small-chart-legend-circle g.highcharts-legend-item rect {
 width: 10px !important;
 height: 10px !important;
 x: 5 !important;
 y: 5 !important;
}

.medium-chart-legend-circle g.highcharts-legend-item rect {
 width: 12px !important;
 height: 12px !important;
 x: 3 !important;
 y: 4 !important;
}

.large-chart-legend-circle g.highcharts-legend-item rect {
 width: 15px !important;
 height: 15px !important;
 x: 2 !important;
 y: 2 !important;
}

.extralarge-chart-legend-circle g.highcharts-legend-item rect {
 width: 18px !important;
 height: 18px !important;
 x: 0 !important;
 y: 0 !important;
}

.centered-tooltip .highcharts-tooltip .highcharts-tooltip-container {
 text-align: center;
}

.centered-tooltip .ods-highcharts__tooltip {
 justify-content: center;
}

.no-background rect.highcharts-background, .no-bg rect.highcharts-background, .remove-background rect.highcharts-background, .transparent-background rect.highcharts-background {
 fill: transparent !important;
}

.ods-highcharts__tooltip {
 align-items: center;
}

g.highcharts-legend-item rect {
 rx: 100%;
 ry: 100%;
}

/* Map legend 
.odswidget-legend__index {
-webkit-box-pack: left !important;
-ms-flex-pack: left !important;
justify-content: left !important; }*/
.indications-cartes {
 font-size: 1.3rem;
}

.map-container {
 max-height: 620px;
 padding: 15px;
 background-color: white;
}

/* ODS LEGEND HORIZONTAL */
.legend-horizontal {
 width: 100%;
 border-radius: 6px;
 margin: 13px 0;
}

.legend-horizontal ul.odswidget-legend__indexes.odswidget-legend__steps_style {
 flex-direction: row;
 justify-content: normal;
 flex-wrap: wrap;
}

/* Style of your page goes here (Fred's POC) */
svg a path {
 stroke: #7f7e7e;
 stroke-width: 2px;
}

svg a text {
 display: none;
 font-size: 1.3em;
 font-weight: 300;
 font-family: sans-serif;
 fill: white !important;
 text-shadow: 2px 2px 5px black;
 stroke: none;
 pointer-events: none;
}

svg a:hover {
 text-decoration: none;
}

svg a:hover text {
 display: inherit;
}

svg a:hover path {
 stroke: white;
 opacity: 0.9;
 stroke-width: 4px;
}

svg a.selected text {
 display: inherit;
}

svg a.selected path {
 stroke-width: 4px;
 stroke: black;
}

/*svg a.unselected path {
opacity: 0.65; }*/
svg use {
 pointer-events: none;
}

/* Style SVG département/*
/* Position en colonne right */
.svgmap-drom.svgmap-drom-right {
 display: -webkit-box;
 display: -ms-flexbox;
 display: flex;
 -webkit-box-orient: vertical;
 -webkit-box-direction: normal;
 -ms-flex-direction: column;
 flex-direction: column;
 position: absolute;
 right: 1%;
 top: 3%;
 width: 11%;
}

/****** Ile de France ZOOM ********/
/* Position Top Left */
.svgmap-idf-top-left ~ .svgmap-francemetro {
 padding-top: 7%;
 padding-left: 7%;
}

.svgmap-idf.svgmap-idf-top-left {
 position: absolute;
 left: 2%;
 top: 2%;
 width: 20%;
}

/* DROM Right + IDF Top Left */
.svgmap-drom-right ~ .svgmap-idf.svgmap-idf-top-left {
 left: 3%;
}

/* Some CSS override to manage picto sizes */
.svgmap svg {
 height: 100%;
 width: 100%;
}

/* None styles */
.svgmap-idf-none,
.svgmap-drom-none {
 display: none;
}

/******** SVG MAPS *************/
/************ Conteneur France ***************/
.svgmap-france {
 width: 100%;
 margin: auto;
 position: relative;
 background-color: white;
}

/* France Métropole */
.svgmap-francemetro {
 padding: 0;
}

/* Custom positionning */
/* DEP */
#text-idf-92 {
 text-anchor: start;
}

#text-29,
#text-22 {
 text-anchor: start;
}

#text-2A,
#text-2B {
 text-anchor: end;
}

/* COM */
#text-978 {
 font-size: 1.2em;
 text-anchor: start;
}

#text-977 {
 text-anchor: end;
 font-size: 1em;
}

#text-975 {
 font-size: 0.75em;
}

#text-988 {
 font-size: 0.95em;
}

.text-ie {
 display: none;
}

/* Style SVG région/*
/* Position en colonne right */
.svgmapregion-drom.svgmapregion-drom-right {
 display: -webkit-box;
 display: -ms-flexbox;
 display: flex;
 -webkit-box-orient: vertical;
 -webkit-box-direction: normal;
 -ms-flex-direction: column;
 flex-direction: column;
 position: absolute;
 right: 1%;
 top: 3%;
 width: 11%;
}

/****** Ile de France ZOOM ********/
/* Position Top Left */
.svgmapregion-idf-top-left ~ .svgmapregion-francemetro {
 padding-top: 7%;
 padding-left: 7%;
}

.svgmapregion-idf.svgmapregion-idf-top-left {
 position: absolute;
 left: 2%;
 top: 2%;
 width: 20%;
}

/* DROM Right + IDF Top Left */
.svgmapregion-drom-right ~ .svgmapregion-idf.svgmapregion-idf-top-left {
 left: 3%;
}

/* Some CSS override to manage picto sizes */
.svgmapregion svg {
 height: 100%;
 width: 100%;
}

/* None styles */
.svgmapregion-idf-none,
.svgmapregion-drom-none {
 display: none !important;
}

/******** SVG MAPS *************/
/************ Conteneur France ***************/
.svgmapregion-france {
 width: auto;
 margin: auto;
 position: relative;
 background-color: white;
}

/* France Métropole */
.svgmapregion-francemetro {
 padding: 0;
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
.fr-select,.odswidget-select-button { background-color:#eee !important;}
.odswidget-select-button {
 background-color: #eee !important;
 padding-left: 15px;
 font-size: 16px;
 border: unset;
 border-bottom: 3px solid #000;
 border-radius: 0px;
}
.odswidget-select-input-container {

 background: #eee;
}
.odswidget-select-button .fa { font-size: 23px;
}
.odswidget-select-button:hover {
 border: unset;
 border-bottom: 3px solid #000;

}
