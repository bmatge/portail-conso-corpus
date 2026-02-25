/* global d3 */
if (typeof d3 === 'undefined') {
  console.warn('D3.js doit etre charge avant taxonomy-tree.js');
}

/**
 * Visualisation arborescente de la taxonomie DGCCRF via D3.
 */
export class TaxonomyTree {
  constructor(wrapperId, taxonomy) {
    this.wrap     = document.getElementById(wrapperId);
    this.taxonomy = taxonomy;
    this.state    = 'idle';   // idle | narrowing | found | hors
    this.foundId  = null;
    this.candidates = [];
    this.dur      = 550;

    // Derive colors, short labels and emojis from taxonomy data
    this.ICON_EMOJI = {
      'fr-icon-warning-fill': '⚠️',
      'fr-icon-file-text-fill': '📋',
      'fr-icon-price-tag-3-fill': '🏷️',
      'fr-icon-restaurant-fill': '🍽️',
      'fr-icon-computer-fill': '💻',
      'fr-icon-building-fill': '🏢',
      'fr-icon-shield-fill': '🛡️',
      'fr-icon-bar-chart-box-fill': '📊',
      'fr-icon-home-4-fill': '🏠',
      'fr-icon-bank-fill': '🏦',
      'fr-icon-scales-fill': '⚖️',
      'fr-icon-heart-fill': '🕊️',
    };
    this.COLORS = taxonomy.domaines.map(d => d.couleur || '#888');
    this.DOMAIN_SHORT = taxonomy.domaines.map(d => this._shortLabel(d.label));
    this.DOMAIN_EMOJI = taxonomy.domaines.map(d => this.ICON_EMOJI[d.icone] || '📌');

    this.lookup = {};
    taxonomy.domaines.forEach((d, di) => {
      d.sous_domaines.forEach(ss => {
        ss.situations.forEach(sit => {
          this.lookup[sit.id] = { sit, ss, domaine: d, di };
        });
      });
    });

    this._buildLegend();
    this._initSVG();
    this._draw();
  }

  _buildLegend() {
    const el = document.getElementById('tree-legend');
    if (!el) return;
    el.innerHTML = this.taxonomy.domaines.map((d, i) => `
      <div class="tree-legend-item">
        <div class="tree-legend-dot" style="background:${this.COLORS[i]}"></div>
        <span>${this.DOMAIN_SHORT[i]}</span>
      </div>
    `).join('');
  }

  _initSVG() {
    this.tooltip = document.getElementById('tree-tooltip');
    const rect = this.wrap.getBoundingClientRect();
    this.W = rect.width  || 600;
    this.H = rect.height || 500;

    this.zoomBeh = d3.zoom()
      .scaleExtent([0.08, 4])
      .on('zoom', e => this.g.attr('transform', e.transform));

    this.svg = d3.select(this.wrap)
      .append('svg')
      .attr('width', '100%')
      .attr('height', '100%')
      .style('background', 'transparent');

    this.svg.call(this.zoomBeh);

    const defs = this.svg.append('defs');
    const f = defs.append('filter').attr('id', 'glow-tree')
      .attr('x', '-50%').attr('y', '-50%').attr('width', '200%').attr('height', '200%');
    f.append('feGaussianBlur').attr('in', 'SourceGraphic').attr('stdDeviation', '5').attr('result', 'blur');
    const m = f.append('feMerge');
    m.append('feMergeNode').attr('in', 'blur');
    m.append('feMergeNode').attr('in', 'SourceGraphic');

    this.g = this.svg.append('g');
    this.gLinks = this.g.append('g').attr('class', 'tree-links');
    this.gNodes = this.g.append('g').attr('class', 'tree-nodes');
  }

  _buildData() {
    const { state, foundId, candidates } = this;
    const tax = this.taxonomy;

    if (state === 'idle') {
      return {
        id: 'root', label: 'DGCCRF', type: 'root',
        children: tax.domaines.map((d, di) => ({
          id: d.id, type: 'domaine', di,
          label: this.DOMAIN_SHORT[di],
          fullLabel: d.label,
          count: d.sous_domaines.reduce((s, ss) => s + ss.situations.length, 0),
        }))
      };
    }

    const relDomainIds = new Set();
    const relSsIds     = new Set();
    const relSitIds    = new Set(candidates);

    candidates.forEach(id => {
      const info = this.lookup[id];
      if (info) { relDomainIds.add(info.domaine.id); relSsIds.add(info.ss.id); }
    });

    return {
      id: 'root', label: 'DGCCRF', type: 'root',
      children: tax.domaines.map((d, di) => {
        const isRel = relDomainIds.has(d.id);
        const node = {
          id: d.id, type: 'domaine', di,
          label: this.DOMAIN_SHORT[di],
          fullLabel: d.label,
          count: d.sous_domaines.reduce((s, ss) => s + ss.situations.length, 0),
          dimmed: !isRel,
        };
        if (isRel) {
          const relSs = d.sous_domaines.filter(ss => relSsIds.has(ss.id));
          node.children = relSs.map(ss => {
            const ssNode = {
              id: ss.id, type: 'sous_domaine', di,
              label: this._short(ss.label, 22),
              fullLabel: ss.label,
            };
            if (state === 'found') {
              const relSits = ss.situations.filter(s => relSitIds.has(s.id));
              if (relSits.length) {
                ssNode.children = relSits.map(sit => ({
                  id: sit.id, type: 'situation', di,
                  label: this._short(sit.label, 28),
                  fullLabel: sit.label,
                  active: sit.id === foundId,
                }));
              }
            }
            return ssNode;
          });
        }
        return node;
      })
    };
  }

  // Coordonnees pour arbre horizontal (gauche→droite) :
  // d3.tree produit n.x = position verticale, n.y = profondeur
  // On swap : ecranX = n.y (profondeur), ecranY = n.x (spread)
  _sx(d) { return d.y; }
  _sy(d) { return d.x; }

  _draw() {
    const data = this._buildData();
    const root = d3.hierarchy(data);

    // nodeSize : [espacement vertical entre freres, espacement horizontal entre niveaux]
    const nSpread = this.state === 'idle' ? 50 : 40;
    const nDepth  = this.state === 'found' ? 160 : 140;

    d3.tree()
      .nodeSize([nSpread, nDepth])
      .separation((a, b) => {
        if (a.parent === b.parent) return (a.data.dimmed || b.data.dimmed) ? .8 : 1.2;
        return 1.5;
      })(root);

    const nodes = root.descendants();
    const links = root.links();

    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    nodes.forEach(n => {
      const sx = this._sx(n), sy = this._sy(n);
      x0 = Math.min(x0, sx); x1 = Math.max(x1, sx);
      y0 = Math.min(y0, sy); y1 = Math.max(y1, sy);
    });

    let fitNodes = nodes;
    if (this.state === 'found') {
      fitNodes = nodes.filter(n => !n.data.dimmed && n.data.type !== undefined);
      if (fitNodes.length === 0) fitNodes = nodes;
      x0 = Math.min(...fitNodes.map(n => this._sx(n))); x1 = Math.max(...fitNodes.map(n => this._sx(n)));
      y0 = Math.min(...fitNodes.map(n => this._sy(n))); y1 = Math.max(...fitNodes.map(n => this._sy(n)));
    }

    const pad = 60;
    const tW = x1 - x0 + pad * 2;
    const tH = y1 - y0 + pad * 2;
    const scale = Math.min((this.W - 40) / tW, (this.H - 40) / tH, this.state === 'found' ? 1.4 : 1.1);
    const tx = pad + (-x0) * scale;
    const ty = this.H / 2 - ((y0 + y1) / 2) * scale;

    this.svg.transition().duration(this.dur)
      .call(this.zoomBeh.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));

    // Liens horizontaux (gauche→droite)
    const self = this;
    const linkPath = d3.linkHorizontal()
      .x(d => self._sx(d))
      .y(d => self._sy(d));

    this.gLinks.selectAll('path.tlink')
      .data(links, d => d.target.data.id)
      .join(
        enter => enter.append('path').attr('class', 'tlink')
          .attr('d', d => {
            const p = { x: d.source.x, y: d.source.y };
            return linkPath({ source: p, target: p });
          })
          .attr('fill', 'none')
          .attr('stroke', d => this._linkColor(d.target))
          .attr('stroke-width', d => d.target.data.active ? 2.5 : 1.5)
          .attr('opacity', 0)
          .call(e => e.transition().duration(this.dur)
            .attr('d', linkPath)
            .attr('opacity', d => d.target.data.dimmed ? 0.07 : 0.4)),
        update => update.transition().duration(this.dur)
          .attr('d', linkPath)
          .attr('stroke', d => this._linkColor(d.target))
          .attr('stroke-width', d => d.target.data.active ? 2.5 : 1.5)
          .attr('opacity', d => d.target.data.dimmed ? 0.07 : 0.4),
        exit => exit.transition().duration(this.dur / 2).attr('opacity', 0).remove()
      );

    this.gNodes.selectAll('g.tnode')
      .data(nodes, d => d.data.id)
      .join(
        enter => {
          const ng = enter.append('g').attr('class', 'tnode')
            .attr('transform', d => {
              const px = d.parent ? self._sx(d.parent) : self._sx(d);
              const py = d.parent ? self._sy(d.parent) : self._sy(d);
              return `translate(${px},${py})`;
            })
            .style('cursor', 'pointer')
            .on('mouseenter', (e, d) => self._showTooltip(e, d))
            .on('mousemove',  (e) => self._moveTooltip(e))
            .on('mouseleave', () => self._hideTooltip());

          ng.append('circle')
            .attr('r', d => self._r(d))
            .attr('fill', d => self._fill(d))
            .attr('stroke', d => self._stroke(d))
            .attr('stroke-width', d => d.data.active ? 3 : 1.5)
            .attr('filter', d => d.data.active ? 'url(#glow-tree)' : null)
            .attr('opacity', 0);

          ng.filter(d => d.data.type === 'domaine')
            .append('text')
            .attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
            .attr('font-size', d => d.data.dimmed ? '10px' : '13px')
            .attr('pointer-events', 'none')
            .text(d => self.DOMAIN_EMOJI[d.data.di] || '');

          ng.filter(d => d.data.type === 'root')
            .append('text')
            .attr('text-anchor', 'middle').attr('dominant-baseline', 'central')
            .attr('font-size', '14px').attr('pointer-events', 'none')
            .text('🏛️');

          // Label a droite du noeud (arbre horizontal)
          ng.append('text')
            .attr('class', 'tnode-label')
            .attr('text-anchor', 'start')
            .attr('x', d => self._r(d) + 6)
            .attr('dominant-baseline', 'central')
            .attr('font-size', d => self._labelSize(d))
            .attr('font-weight', d => d.data.active ? '700' : (d.data.type === 'root' ? '700' : '400'))
            .attr('fill', d => d.data.dimmed ? '#bbb' : (d.data.active ? self.COLORS[d.data.di] : '#333'))
            .attr('pointer-events', 'none')
            .text(d => d.data.label || '');

          ng.filter(d => d.data.type === 'domaine' && !d.data.dimmed && d.data.count)
            .append('text').attr('class', 'tnode-count')
            .attr('text-anchor', 'start')
            .attr('x', d => self._r(d) + 6)
            .attr('y', 12)
            .attr('font-size', '8.5px').attr('fill', '#aaa')
            .attr('pointer-events', 'none')
            .text(d => `${d.data.count} sit.`);

          ng.filter(d => d.data.active)
            .append('text').attr('class', 'tnode-badge')
            .attr('text-anchor', 'middle')
            .attr('y', d => -(self._r(d) + 8))
            .attr('font-size', '9px').attr('font-weight', '700')
            .attr('fill', d => self.COLORS[d.data.di] || '#000091')
            .attr('pointer-events', 'none')
            .text('✓ TROUVE');

          ng.transition().duration(self.dur)
            .attr('transform', d => `translate(${self._sx(d)},${self._sy(d)})`);
          ng.select('circle').transition().duration(self.dur)
            .attr('opacity', d => d.data.dimmed ? 0.15 : 1);

          return ng;
        },

        update => {
          update.transition().duration(self.dur)
            .attr('transform', d => `translate(${self._sx(d)},${self._sy(d)})`);

          update.select('circle').transition().duration(self.dur)
            .attr('r',      d => self._r(d))
            .attr('fill',   d => self._fill(d))
            .attr('stroke', d => self._stroke(d))
            .attr('filter', d => d.data.active ? 'url(#glow-tree)' : null)
            .attr('opacity', d => d.data.dimmed ? 0.15 : 1);

          update.select('.tnode-label').transition().duration(self.dur)
            .attr('x', d => self._r(d) + 6)
            .attr('font-size', d => self._labelSize(d))
            .attr('font-weight', d => d.data.active ? '700' : '400')
            .attr('fill', d => d.data.dimmed ? '#bbb' : (d.data.active ? self.COLORS[d.data.di] : '#333'));

          return update;
        },

        exit => exit.transition().duration(self.dur / 2).attr('opacity', 0).remove()
      );

    this.gNodes.selectAll('g.tnode')
      .classed('active-node', d => !!d.data.active);
  }

  _r(d) {
    if (d.data.type === 'root')         return 22;
    if (d.data.type === 'domaine')      return d.data.dimmed ? 10 : 15;
    if (d.data.type === 'sous_domaine') return 10;
    return d.data.active ? 11 : 8;
  }
  _fill(d) {
    if (d.data.dimmed) return '#e0e0e0';
    if (d.data.type === 'root') return '#000091';
    const c = this.COLORS[d.data.di] || '#888';
    if (d.data.active) return c;
    if (d.data.type === 'domaine') return c;
    if (d.data.type === 'sous_domaine') return c + 'bb';
    return c + '77';
  }
  _stroke(d) {
    if (d.data.dimmed) return '#ccc';
    if (d.data.type === 'root') return '#00006b';
    return this.COLORS[d.data.di] || '#888';
  }
  _linkColor(target) {
    if (target.data.di !== undefined) return (this.COLORS[target.data.di] || '#999') + '55';
    return '#ccc';
  }
  _labelSize(d) {
    if (d.data.type === 'root') return '11px';
    if (d.data.type === 'domaine') return d.data.dimmed ? '9px' : '10.5px';
    if (d.data.type === 'sous_domaine') return '9.5px';
    return '9px';
  }
  _short(str, max) {
    return str && str.length > max ? str.slice(0, max - 1) + '…' : (str || '');
  }
  _shortLabel(label) {
    const map = {
      'pratiques commerciales': 'Com. déloyales',
      'contrats': 'Contrats',
      'prix': 'Prix',
      'fraude et sécurité alimentaire': 'Alimentaire',
      'numérique': 'Numérique',
      'secteurs réglementés': 'Secteurs',
      'sécurité des produits': 'Sécurité',
      'pratiques anticoncurrentielles': 'Concurrence',
      'logement': 'Logement',
      'banque': 'Banque',
      'droits du consommateur': 'Droits conso',
      'services funéraires': 'Funéraire',
    };
    const lower = (label || '').toLowerCase();
    for (const [key, short] of Object.entries(map)) {
      if (lower.startsWith(key)) return short;
    }
    // Fallback: first two words, max 15 chars
    const words = label.split(/[\s,]+/).slice(0, 2).join(' ');
    return words.length > 15 ? words.slice(0, 14) + '…' : words;
  }

  _showTooltip(event, d) {
    if (!this.tooltip) return;
    const nd = d.data;
    let html = '';
    if (nd.type === 'root') {
      const nDom = this.taxonomy.domaines.length;
      const nSit = this.taxonomy.domaines.reduce((s, d) => s + d.sous_domaines.reduce((s2, ss) => s2 + ss.situations.length, 0), 0);
      html = `<strong>DGCCRF</strong><br>${nDom} domaines · ${nSit} situations`;
    }
    else if (nd.type === 'domaine') html = `<strong>${nd.fullLabel || nd.label}</strong><br>${nd.count} situations`;
    else if (nd.type === 'sous_domaine') html = `<strong>${nd.fullLabel || nd.label}</strong>`;
    else html = `<strong>${nd.fullLabel || nd.label}</strong>` + (nd.active ? '<br><em>✓ Situation identifiee</em>' : '');
    this.tooltip.innerHTML = html;
    this.tooltip.classList.add('visible');
    this._moveTooltip(event);
  }
  _moveTooltip(event) {
    if (!this.tooltip) return;
    this.tooltip.style.left = (event.clientX + 12) + 'px';
    this.tooltip.style.top  = (event.clientY - 6) + 'px';
  }
  _hideTooltip() {
    if (this.tooltip) this.tooltip.classList.remove('visible');
  }

  // API publique
  showCandidates(ids) {
    if (!ids || ids.length === 0) return;
    this.state = 'narrowing';
    this.candidates = ids;
    this.foundId = null;
    this._draw();
    this._setStateLabel(`Affinage — ${ids.length} situation(s) candidate(s)`);
  }

  showResult(situationId) {
    const info = this.lookup[situationId];
    this.state = 'found';
    this.foundId = situationId;
    this.candidates = [situationId];
    this._draw();
    const label = info ? `${info.domaine.label} › ${info.ss.label}` : situationId;
    this._setStateLabel(`Resultat : ${this._short(label, 50)}`);
  }

  setThinking(on) {
    this.gNodes.selectAll('g.tnode')
      .filter(d => d.data && d.data.type === 'root')
      .select('circle')
      .attr('filter', on ? 'url(#glow-tree)' : null);
  }

  fitAll() {
    this._draw();
  }

  reset() {
    this.state = 'idle';
    this.foundId = null;
    this.candidates = [];
    this._draw();
    this._setStateLabel(`Vue d'ensemble — ${this.taxonomy.domaines.length} domaines`);
  }

  _setStateLabel(txt) {
    const el = document.getElementById('tree-state-label');
    if (el) el.textContent = txt;
  }
}
