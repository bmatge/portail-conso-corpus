import { describe, it, expect } from 'vitest';
import { getSituation, buildResultCard } from '../js/result-card.js';
import { MOCK_TAXONOMY, MOCK_LLM_RESPONSE_FOUND } from './setup.js';

describe('getSituation', () => {
  it('retourne null pour un id inconnu', () => {
    expect(getSituation(MOCK_TAXONOMY, 'inexistant')).toBeNull();
  });

  it('retourne null si taxonomy est null', () => {
    expect(getSituation(null, 'garage_surfacturation')).toBeNull();
  });

  it('retourne domaine/sous_domaine/situation pour un id connu', () => {
    const result = getSituation(MOCK_TAXONOMY, 'garage_surfacturation');
    expect(result).not.toBeNull();
    expect(result.sit.id).toBe('garage_surfacturation');
    expect(result.ss.id).toBe('automobile');
    expect(result.domaine.id).toBe('secteurs_reglementes');
  });

  it('retrouve aussi la deuxieme situation', () => {
    const result = getSituation(MOCK_TAXONOMY, 'compteur_kilometre_truque');
    expect(result).not.toBeNull();
    expect(result.sit.id).toBe('compteur_kilometre_truque');
  });
});

describe('buildResultCard', () => {
  it('retourne une carte de fallback pour une situation inconnue', () => {
    const html = buildResultCard(MOCK_TAXONOMY, 'inconnu', { confiance: 'haute' });
    expect(html).toContain('inconnu');
    expect(html).toContain('SignalConso');
  });

  it('inclut le domaine et le sous-domaine dans le titre', () => {
    const html = buildResultCard(MOCK_TAXONOMY, 'garage_surfacturation', MOCK_LLM_RESPONSE_FOUND);
    expect(html).toContain('Secteurs reglementes');
    expect(html).toContain('Automobile');
  });

  it('affiche le badge de confiance haute (success)', () => {
    const html = buildResultCard(MOCK_TAXONOMY, 'garage_surfacturation', { confiance: 'haute' });
    expect(html).toContain('fr-badge--success');
    expect(html).toContain('Confiance haute');
  });

  it('affiche le badge de confiance moyenne (warning)', () => {
    const html = buildResultCard(MOCK_TAXONOMY, 'garage_surfacturation', { confiance: 'moyenne' });
    expect(html).toContain('fr-badge--warning');
    expect(html).toContain('Confiance moyenne');
  });

  it('affiche le badge de confiance faible (error)', () => {
    const html = buildResultCard(MOCK_TAXONOMY, 'garage_surfacturation', { confiance: 'faible' });
    expect(html).toContain('fr-badge--error');
    expect(html).toContain('A confirmer');
  });

  it('affiche l\'alerte urgence quand signalconso.urgence est true', () => {
    const html = buildResultCard(MOCK_TAXONOMY, 'compteur_kilometre_truque', { confiance: 'haute' });
    expect(html).toContain('fr-alert--error');
    expect(html).toContain('urgente');
  });

  it('n\'affiche pas l\'alerte urgence quand urgence est false', () => {
    const html = buildResultCard(MOCK_TAXONOMY, 'garage_surfacturation', { confiance: 'haute' });
    expect(html).not.toContain('fr-alert--error');
  });

  it('affiche les sorties avec icones et URLs', () => {
    const html = buildResultCard(MOCK_TAXONOMY, 'garage_surfacturation', { confiance: 'haute' });
    expect(html).toContain('Signaler sur SignalConso');
    expect(html).toContain('signal.conso.gouv.fr');
    expect(html).toContain('Mediateur auto');
  });

  it('affiche le badge SignalConso quand category existe', () => {
    const html = buildResultCard(MOCK_TAXONOMY, 'garage_surfacturation', { confiance: 'haute' });
    expect(html).toContain('fr-tag');
    expect(html).toContain('AchatMagasin');
  });

  it('affiche le bloc mediateur quand le sous-domaine en a un', () => {
    const html = buildResultCard(MOCK_TAXONOMY, 'garage_surfacturation', { confiance: 'haute' });
    expect(html).toContain('Mediateur sectoriel');
    expect(html).toContain('mediateur-automobile.example.fr');
  });

  it('affiche les notes des sorties', () => {
    const html = buildResultCard(MOCK_TAXONOMY, 'garage_surfacturation', { confiance: 'haute' });
    expect(html).toContain('Joignez le devis et la facture.');
  });
});
