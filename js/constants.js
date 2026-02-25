// ════════════════════════════════════════════════════════════
// CONFIG LLM
// ════════════════════════════════════════════════════════════
export const DEFAULT_CONFIG = {
  mode: 'builtin',          // 'builtin' = server-side key via /api/chat, 'custom' = client-side key via proxy
  endpoint: 'https://albert.api.etalab.gouv.fr/v1/chat/completions',
  model: 'openweight-medium',
  apiKey: '',
  format: 'openai',
  temperature: 0.9,
  maxTokens: 320,
};

export const PRESETS = {
  albert:    { endpoint: 'https://albert.api.etalab.gouv.fr/v1/chat/completions', model: 'openweight-medium',         format: 'openai' },
  mistral:   { endpoint: 'https://api.mistral.ai/v1/chat/completions',            model: 'mistral-small-latest',      format: 'openai' },
  openai:    { endpoint: 'https://api.openai.com/v1/chat/completions',             model: 'gpt-4o-mini',              format: 'openai' },
  ollama:    { endpoint: 'http://localhost:11434/v1/chat/completions',              model: 'mistral',                  format: 'openai' },
  anthropic: { endpoint: 'https://api.anthropic.com/v1/messages',                  model: 'claude-haiku-4-5-20251001', format: 'anthropic' },
};

// ════════════════════════════════════════════════════════════
// TAXONOMIE COMPRIMEE (pour le prompt)
// ════════════════════════════════════════════════════════════
export const TAXONOMY_COMPRESSED = `pub_caracteristiques_fausses | Les caracteristiques du produit/service annoncees ne correspondent pas a la realite | Pratiques commerciales deloyales | ex: Produit decrit comme neuf mais reconditionne
pub_prix_mensonger | Le prix reel est superieur au prix annonce (frais caches, conditions non affichees) | Pratiques commerciales deloyales
pub_influenceur_dissimule | Contenu sponsorise d'un influenceur non identifie comme publicite | Pratiques commerciales deloyales
pub_greenwashing | Allegations environnementales mensongeres (greenwashing, faux ecolabel) | Pratiques commerciales deloyales
demarchage_telephonique | Demarchage telephonique non sollicite (hors exceptions legales) | Pratiques commerciales deloyales
demarchage_domicile | Vente a domicile avec pression ou sans remise du bon de retractation | Pratiques commerciales deloyales
abus_faiblesse | Abus de faiblesse ou de vulnerabilite (personne agee, etat de detresse…) | Pratiques commerciales deloyales
faux_avis_client | Des avis clients semblent faux ou achetes | Pratiques commerciales deloyales
suppression_avis_negatifs | Un professionnel fait supprimer des avis negatifs legitimes | Pratiques commerciales deloyales
vente_liee | Obligation d'acheter un produit pour en obtenir un autre (vente liee illegale) | Pratiques commerciales deloyales
abonnement_cache | Souscription a un abonnement sans consentement explicite | Pratiques commerciales deloyales
renouvellement_tacite_sans_preavis | Renouvellement automatique d'un contrat sans information prealable | Pratiques commerciales deloyales
prix_reference_fictif | Le prix barre (prix de reference) n'a jamais ete pratique ou est fictif | Pratiques commerciales deloyales
soldes_irreguliers | Soldes pratiques en dehors des periodes legales sans autorisation | Pratiques commerciales deloyales
retractation_refuse | Le professionnel refuse d'appliquer le droit de retractation de 14 jours | Contrats, garanties et droits du consommateur
retractation_domicile | Le professionnel refuse le droit de retractation pour une vente a domicile | Contrats, garanties et droits du consommateur
non_livraison | Le produit commande n'est pas livre et le vendeur ne repond pas | Contrats, garanties et droits du consommateur
retard_livraison | Retard de livraison significatif sans information ni solution proposee | Contrats, garanties et droits du consommateur
produit_endommage_livraison | Produit recu endommage | Contrats, garanties et droits du consommateur
garantie_conformite_refusee | Le vendeur refuse la garantie legale de conformite (2 ans pour produits neufs) | Contrats, garanties et droits du consommateur
garantie_vices_caches | Defaut cache decouvert apres achat (vice cache) | Contrats, garanties et droits du consommateur
garantie_commerciale_non_respectee | La garantie commerciale du fabricant ou du vendeur n'est pas appliquee | Contrats, garanties et droits du consommateur
clause_resiliation_abusive | Le contrat impose des conditions de resiliation excessivement contraignantes | Contrats, garanties et droits du consommateur
clause_responsabilite_limitee | Une clause exclut ou limite abusivement la responsabilite du professionnel | Contrats, garanties et droits du consommateur
clause_unilaterale_modification | Le professionnel se reserve le droit de modifier unilateralement le contrat | Contrats, garanties et droits du consommateur
sav_non_reponse | Le SAV ne repond pas ou refuse de traiter la demande | Contrats, garanties et droits du consommateur
reparation_facturee_garantie | Une reparation est facturee alors qu'elle devrait etre couverte par la garantie | Contrats, garanties et droits du consommateur
prix_non_affiche | Les prix ne sont pas affiches en magasin ou sur le site | Prix et etiquetage
prix_ttc_non_mentionne | Le prix TTC n'est pas clairement indique | Prix et etiquetage
frais_caches_commande | Des frais apparaissent seulement au moment du paiement | Prix et etiquetage
etiquette_double | Double etiquetage (nouveau prix sur ancien, l'original reste lisible et est different) | Prix et etiquetage
etiquette_mensongere_origine | L'origine du produit indiquee est fausse ou trompeuse | Prix et etiquetage
composition_differente_etiquette | La composition reelle du produit ne correspond pas a l'etiquette | Fraude et securite alimentaire
fraude_bio | Produit vendu comme bio sans certification valide | Fraude et securite alimentaire
fraude_aoc_igp | Usage abusif d'une AOP/IGP/Label Rouge | Fraude et securite alimentaire
origine_geographique_fausse | L'origine geographique annoncee est fausse | Fraude et securite alimentaire
allergenes_absents | Les allergenes ne sont pas mentionnes ou sont masques sur l'etiquette | Fraude et securite alimentaire
date_peremption_manquante | Date de peremption (DLC/DDM) absente ou illisible | Fraude et securite alimentaire
produit_perime_vendu | Des produits perimes sont en vente | Fraude et securite alimentaire
allegations_nutritionnelles_fausses | Allegations nutritionnelles ou de sante fausses ou non autorisees | Fraude et securite alimentaire
complement_allegations_medicales | Un complement alimentaire est presente comme un medicament | Fraude et securite alimentaire
complement_substance_interdite | Presence suspectee d'une substance interdite dans un complement alimentaire | Fraude et securite alimentaire
hygiene_restauration | Probleme d'hygiene grave dans un restaurant | Fraude et securite alimentaire
tromperie_carte_restaurant | Produits du menu differents de ce qui est servi | Fraude et securite alimentaire
intoxication_alimentaire | Intoxication alimentaire (toxi-infection alimentaire collective suspectee) | Fraude et securite alimentaire
faux_site_commerce | Faux site de vente en ligne : commande et paye, rien recu, site disparu | Numerique, cyber et commerce en ligne
phishing | Hameconnage (phishing) : faux email/SMS imitant un organisme officiel | Numerique, cyber et commerce en ligne
faux_site_gouvernemental | Faux site imitant un service public pour obtenir des paiements indus | Numerique, cyber et commerce en ligne
arnaque_support_technique | Arnaque au support technique (fausse alerte virus, prise en main non sollicitee) | Numerique, cyber et commerce en ligne
arnaque_investissement | Placement financier frauduleux (crypto, forex, rendements eleves promis) | Numerique, cyber et commerce en ligne
vendeur_marketplace_defaillant | Un vendeur tiers sur une marketplace ne livre pas ou vend un produit defectueux | Numerique, cyber et commerce en ligne
plateforme_classement_opaque | Les resultats ou avis sur une plateforme semblent manipules | Numerique, cyber et commerce en ligne
dark_pattern_abonnement | Un abonnement active suite a une interface concue pour tromper | Numerique, cyber et commerce en ligne
dark_pattern_cookies | Impossible de refuser les cookies aussi facilement qu'on peut les accepter | Numerique, cyber et commerce en ligne
dark_pattern_resiliation | La resiliation d'un service en ligne est deliberement complexifiee | Numerique, cyber et commerce en ligne
donnees_vendues_tiers | Mes donnees personnelles ont ete transmises ou vendues a des tiers sans consentement | Numerique, cyber et commerce en ligne
droit_acces_refuse | Un site refuse d'exercer mon droit d'acces, de rectification ou de suppression | Numerique, cyber et commerce en ligne
promo_produit_sante_influenceur | Un influenceur promeut un produit de sante ou financier de facon trompeuse | Numerique, cyber et commerce en ligne
partenariat_non_declare | Un partenariat commercial n'est pas declare dans une publication ou video | Numerique, cyber et commerce en ligne
agence_honoraires_abusifs | Honoraires d'agence immobiliere non affiches, abusifs ou non conformes loi Alur | Secteurs reglementes
diagnostic_errone | Diagnostic immobilier (DPE, amiante…) errone ou frauduleux | Secteurs reglementes
location_logement_non_conforme | Logement loue non conforme (DPE mensonger, surfaces fausses) | Secteurs reglementes
teg_errone | Taux d'interet ou TAEG errone ou non communique | Secteurs reglementes
credit_revolving_abusif | Credit renouvelable propose de facon agressive ou sans verification de solvabilite | Secteurs reglementes
assurance_emprunteur_refus | Refus illegal de substitution d'assurance emprunteur | Secteurs reglementes
vol_annule_remboursement_refuse | Vol annule et la compagnie refuse le remboursement | Secteurs reglementes
sejour_non_conforme | Le sejour ou le voyage a forfait ne correspond pas a ce qui etait decrit | Secteurs reglementes
agence_voyage_defaillante | L'agence de voyages a fait faillite ou n'execute pas le contrat | Secteurs reglementes
demarchage_energie_abusif | Demarchage abusif d'un fournisseur d'energie (pression, faux EDF) | Secteurs reglementes
facture_energie_anormale | Facture d'energie anormalement elevee ou inexpliquee | Secteurs reglementes
resiliation_energie_bloquee | Resiliation du contrat d'energie bloquee ou frais abusifs | Secteurs reglementes
voiture_occasion_vices | Voiture d'occasion vendue avec des defauts caches | Secteurs reglementes
garage_surfacturation | Garage : facturation de reparations non effectuees ou devis non respecte | Secteurs reglementes
compteur_kilometre_truque | Compteur kilometrique manifestement truque sur un vehicule d'occasion | Secteurs reglementes
operateur_resiliation_difficile | L'operateur telephonique rend la resiliation difficile ou facture des penalites | Secteurs reglementes
service_non_conforme_offre | Le service fourni ne correspond pas a l'offre souscrite | Secteurs reglementes
surcharge_facture_telecom | Surcharges incomprehensibles sur la facture telephonique | Secteurs reglementes
sinistre_rembourse_insuffisamment | Indemnisation suite a un sinistre refusee ou sous-evaluee | Secteurs reglementes
resiliation_assurance_abusive | Resiliation abusive d'un contrat d'assurance | Secteurs reglementes
organisme_formation_frauduleux | Organisme de formation qui percoit des fonds CPF sans dispenser la formation | Secteurs reglementes
diplome_bidon | Diplome ou certification bidon vendu a prix eleve | Secteurs reglementes
cosmetique_non_conforme | Produit cosmetique provoquant des effets indesirables graves ou non conforme | Secteurs reglementes
medecine_douce_arnaque | Praticien de medecine alternative facturant des soins inefficaces comme curatifs | Secteurs reglementes
jouet_dangereux | Jouet dangereux (pieces detachables, absence marquage CE, materiaux toxiques) | Securite des produits
produit_electrique_dangereux | Appareil electrique provoquant des chocs, surchauffe ou incendie | Securite des produits
produit_chimique_dangereux | Produit chimique sans etiquetage de danger ou non conforme | Securite des produits
produit_sous_rappel | Je pense avoir achete un produit faisant l'objet d'un rappel | Securite des produits
marquage_ce_absent | Un produit vendu en France ne porte pas le marquage CE obligatoire | Securite des produits
entente_prix | Des concurrents s'entendent sur les prix ou se repartissent le marche (cartel) | Pratiques anticoncurrentielles
conditions_abusives_fournisseur | Un partenaire dominant impose des conditions contractuelles abusives | Pratiques anticoncurrentielles
delais_paiement_depasses | Un client depasse les delais de paiement legaux (60 jours en general) | Pratiques anticoncurrentielles
rupture_brutale_relations | Rupture brutale de relations commerciales etablies sans preavis | Pratiques anticoncurrentielles`;

// ════════════════════════════════════════════════════════════
// PROMPT SYSTEME
// ════════════════════════════════════════════════════════════
export const SYSTEM_PROMPT = `Tu es un assistant de flechage pour les consommateurs francais, opere par la DGCCRF.

LISTE DES SITUATIONS (format : id | libelle | domaine) :
${TAXONOMY_COMPRESSED}

REGLES STRICTES :
1. Tu reponds UNIQUEMENT en JSON valide, sans aucun texte avant ou apres.
2. Si le probleme correspond clairement a une situation → retourne situation_id + confiance "haute" ou "moyenne".
3. Si tu hesites entre plusieurs situations → retourne question_clarification + candidate_situation_ids (liste des ids hesitants) + situation_id null.
4. Si hors perimetre DGCCRF → hors_perimetre: true.
5. Ne jamais inventer un situation_id absent de la liste.

FORMAT DE REPONSE OBLIGATOIRE (JSON strict) :
{
  "situation_id": "string | null",
  "confiance": "haute | moyenne | faible",
  "question_clarification": "string | null",
  "candidate_situation_ids": [],
  "hors_perimetre": false
}`;

// ════════════════════════════════════════════════════════════
// CONSTANTES SORTIES
// ════════════════════════════════════════════════════════════
export const SORTIE_ICONS = {
  signal_conso: '🚨', mediation: '🤝', service_public: '📋',
  autorite_cnil: '🔒', autorite_arcom: '📡', autorite_amf: '💹',
  autorite_dgal: '🌾', autorite_ansm: '💊', autorite_acpr: '🏦',
  autorite_arcep: '📶', juridiction: '⚖️', police_gendarmerie: '👮',
  '17cyber': '🛡️', cybermalveillance: '💻', rappelconso: '⚠️',
};

export const SORTIE_LABELS = {
  signal_conso: 'SignalConso', mediation: 'Mediation de la consommation',
  service_public: 'Service-Public.fr', autorite_cnil: 'CNIL',
  autorite_arcom: 'ARCOM', autorite_amf: 'Autorite des Marches Financiers',
  autorite_dgal: 'DGAL / DDPP', autorite_ansm: 'ANSM',
  autorite_acpr: 'ACPR', autorite_arcep: 'ARCEP',
  juridiction: 'Recours judiciaire', police_gendarmerie: 'Depot de plainte',
  '17cyber': '17Cyber', cybermalveillance: 'Cybermalveillance.gouv.fr',
  rappelconso: 'RappelConso',
};
