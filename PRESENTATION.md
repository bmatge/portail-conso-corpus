# Assistant Consommateur DGCCRF — Présentation fonctionnelle

## Le constat

Quand un consommateur rencontre un problème — un artisan qui ne termine pas ses travaux, un colis jamais livré, une clause abusive dans un contrat — il se retrouve face à un maquis d'informations dispersées entre plusieurs sites institutionnels (DGCCRF, service-public.fr, INC, SignalConso). Identifier le bon interlocuteur et la bonne démarche demande du temps, de la persévérance, et souvent des connaissances juridiques que le citoyen n'a pas.

Du côté de l'administration, l'information existe : plus de 5 500 fiches réparties sur quatre sources documentaires. Mais elle est fragmentée, parfois redondante, rédigée dans un registre juridique, et structurée selon une logique institutionnelle plutôt que selon le parcours du consommateur.

## Ce que fait l'application

L'Assistant Consommateur est un prototype qui répond à une question simple : **peut-on transformer cette masse documentaire en un service d'orientation immédiat, en langage courant, qui guide chaque consommateur vers le bon recours ?**

### Trois modes d'accès complémentaires

**L'assistant conversationnel** — Le consommateur décrit son problème avec ses propres mots : *« Mon garagiste m'a facturé une réparation qu'il n'a pas faite »*, *« J'ai acheté un meuble sur internet et il est arrivé cassé »*. L'assistant identifie la situation dans le référentiel DGCCRF et propose les démarches adaptées : signalement sur SignalConso, saisine du médiateur compétent, recours auprès de l'autorité concernée (CNIL, ARCOM, AMF…), avec les liens directs.

**Les fiches pratiques** — 267 fiches structurées couvrant l'intégralité du périmètre DGCCRF : 12 grands domaines (pratiques commerciales, numérique, logement, alimentaire, banque…), 60 sous-domaines, 192 situations concrètes. Chaque fiche suit un format homogène : un résumé « en bref », le périmètre couvert, les droits du consommateur, les démarches à suivre, les services compétents, et des ressources complémentaires.

**La recherche sémantique** — Une recherche en langage naturel qui interroge simultanément les quatre corpus sources et les fiches générées. Le consommateur tape *« garantie téléphone reconditionné »* et obtient les résultats les plus pertinents, classés par score de similarité, avec accès direct aux fiches pratiques associées.

### Un référentiel unifié

L'ensemble repose sur une **taxonomie structurée** (le référentiel DGCCRF v3.0) qui organise tout le champ de la consommation en arbre de décision. Cette taxonomie fait le lien entre :

- les **situations vécues** par le consommateur (192 cas concrets)
- les **types de recours** disponibles (17 : SignalConso, médiation, CNIL, ARCOM, AMF, tribunal, etc.)
- les **catégories SignalConso** pour le signalement direct
- les **sources documentaires** existantes

L'arbre de décision est visualisé de façon interactive dans l'interface : chaque domaine a sa couleur et son pictogramme, et l'arbre s'anime en temps réel pendant la conversation pour montrer le cheminement du diagnostic.

## Ce que le prototype explore

### La rédaction augmentée par l'IA

Les 267 fiches n'ont pas été rédigées manuellement. Elles ont été **générées par un pipeline de rédaction assistée** (RAG — Retrieval-Augmented Generation) :

1. Les 5 500 fiches sources sont découpées et indexées dans une base vectorielle
2. Pour chaque item de la taxonomie, le système retrouve les contenus les plus pertinents dans les quatre corpus
3. Un modèle de langage (Albert, le LLM souverain de la DINUM) rédige la fiche en synthétisant ces sources, selon un gabarit normé
4. La génération est **bottom-up** : les fiches « situation » sont rédigées d'abord, puis les fiches « sous-domaine » résument leurs situations, et les fiches « domaine » offrent une vue d'ensemble

Ce processus permet de produire en quelques heures un corpus structuré et homogène qui aurait demandé des mois de rédaction manuelle. Les fiches restent éditables et auditables : chaque source utilisée est traçable.

### L'orientation conversationnelle

Le chatbot ne se contente pas de chercher des mots-clés. Il **comprend la situation décrite** et la met en correspondance avec le référentiel. Un consommateur qui écrit *« on m'a livré un frigo qui ne marche pas »* sera orienté vers la garantie légale de conformité, avec le lien SignalConso pré-rempli pour la bonne catégorie. La conversation peut se poursuivre pour affiner le diagnostic.

### La souveraineté numérique

Le prototype utilise **Albert**, le modèle de langage de la DINUM, hébergé sur l'infrastructure de l'État. Aucune donnée ne transite par des serveurs privés américains. L'architecture est néanmoins modulaire : l'interface supporte aussi Mistral, OpenAI ou un modèle local (Ollama), ce qui permet de comparer les performances et de s'adapter aux évolutions technologiques.

## Ce que ça permet d'envisager

### À court terme

- **Mise à disposition en interne** — Un outil d'aide aux agents DGCCRF (DD, DDPP) pour répondre plus rapidement aux sollicitations des consommateurs, avec des réponses normalisées et sourcées.
- **Complément à SignalConso** — Un pré-diagnostic qui oriente le consommateur vers la bonne catégorie de signalement avant qu'il ne remplisse le formulaire, réduisant les signalements mal orientés.
- **Base de connaissances actualisable** — Le pipeline de génération peut être relancé à chaque évolution réglementaire ou enrichissement des sources. La mise à jour du corpus complet prend moins d'une heure.

### À moyen terme

- **Déploiement multi-canal** — Le moteur conversationnel peut alimenter un widget intégrable sur les sites partenaires (service-public.fr, INC, associations de consommateurs), un agent vocal, ou un canal de messagerie.
- **Personnalisation territoriale** — Les fiches pourraient intégrer les coordonnées des DD/DDPP locales, des médiateurs de la consommation par secteur, et des associations agréées selon le département.
- **Tableau de bord analytique** — Les requêtes des consommateurs constituent un signal en temps réel sur les problématiques émergentes : nouvelles arnaques, secteurs en tension, pics saisonniers. Ces données pourraient alimenter le pilotage des contrôles.

### En termes de méthode

Ce prototype illustre une approche **reproductible** pour d'autres administrations confrontées au même défi : un corpus documentaire vaste, hétérogène, difficile d'accès pour l'usager. Le pipeline (taxonomie → indexation → génération RAG → interface conversationnelle) peut s'adapter à d'autres domaines : droit du travail, fiscalité, urbanisme, santé publique.

Les briques sont souveraines (Albert, infrastructure DINUM), le code est ouvert, et l'architecture est volontairement simple (HTML/JS statique + API Python) pour rester maintenable par une petite équipe.

---

*Prototype réalisé par la Mission Ingénierie du Web (MIWEB), SNUM — Février 2026.*
