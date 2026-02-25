/**
 * Fixtures partagees pour les tests.
 */

export const MOCK_TAXONOMY = {
  meta: { contenu: { domaines: 1, sous_domaines: 1, situations: 2 } },
  types_sortie: {
    signal_conso: { url: 'https://signal.conso.gouv.fr' },
    mediation: { url: 'https://www.economie.gouv.fr/mediation-conso' },
  },
  domaines: [
    {
      id: 'secteurs_reglementes',
      label: 'Secteurs reglementes',
      sous_domaines: [
        {
          id: 'automobile',
          label: 'Automobile',
          mediateur: {
            label: 'Mediateur automobile',
            url: 'https://mediateur-automobile.example.fr',
          },
          situations: [
            {
              id: 'garage_surfacturation',
              label: 'Garage : facturation de reparations non effectuees ou devis non respecte',
              signalconso: {
                category: 'AchatMagasin',
                urgence: false,
              },
              sorties: [
                {
                  type: 'signal_conso',
                  label: 'Signaler sur SignalConso',
                  url: 'https://signal.conso.gouv.fr',
                  priorite: 1,
                  note: 'Joignez le devis et la facture.',
                },
                {
                  type: 'mediation',
                  label: 'Mediateur auto',
                  url: 'https://mediateur-automobile.example.fr',
                  priorite: 2,
                },
              ],
            },
            {
              id: 'compteur_kilometre_truque',
              label: 'Compteur kilometrique manifestement truque',
              signalconso: {
                category: 'AchatMagasin',
                urgence: true,
              },
              sorties: [
                {
                  type: 'signal_conso',
                  label: 'Signaler sur SignalConso',
                  url: 'https://signal.conso.gouv.fr',
                  priorite: 1,
                },
                {
                  type: 'police_gendarmerie',
                  label: 'Depot de plainte',
                  url: 'https://www.pre-plainte-en-ligne.gouv.fr',
                  priorite: 1,
                  note: 'Fraude penale — deposez plainte.',
                },
              ],
            },
          ],
        },
      ],
    },
  ],
};

export const MOCK_LLM_RESPONSE_FOUND = {
  situation_id: 'garage_surfacturation',
  confiance: 'haute',
  question_clarification: null,
  candidate_situation_ids: [],
  hors_perimetre: false,
};

export const MOCK_LLM_RESPONSE_CLARIFICATION = {
  situation_id: null,
  confiance: 'faible',
  question_clarification: 'Pouvez-vous preciser si le probleme concerne le devis ou la facture ?',
  candidate_situation_ids: ['garage_surfacturation', 'compteur_kilometre_truque'],
  hors_perimetre: false,
};

export const MOCK_LLM_RESPONSE_HORS = {
  situation_id: null,
  confiance: 'faible',
  question_clarification: null,
  candidate_situation_ids: [],
  hors_perimetre: true,
};
