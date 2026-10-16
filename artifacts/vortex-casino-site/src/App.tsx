import { useState } from 'react';
import { ArrowDownRight, ArrowUpRight, Menu, ShieldCheck, X } from 'lucide-react';

const DISCORD_INVITE_URL =
  'https://discord.com/oauth2/authorize?client_id=1501260230883803146&permissions=1099780074518&scope=bot%20applications.commands';

const ranks = [
  'VIP',
  'Viciado',
  'Supremo',
  'Bronce',
  'Plata',
  'Oro',
  'Diamante',
  'Ruby',
  'Esmeralda',
  'Zafiro',
  'Obsidiana',
];

const moderationCommands = [
  { command: '/ban', action: 'Expulsar de forma permanente' },
  { command: '/unban', action: 'Retirar un veto' },
  { command: '/kick', action: 'Expulsar del servidor' },
  { command: '/mute · /unmute', action: 'Silenciar o devolver la voz' },
  { command: '/lock · /unlock', action: 'Cerrar o abrir un canal' },
  { command: '/clear', action: 'Borrar mensajes' },
  { command: '/addrole · /removerole', action: 'Añadir o retirar roles' },
];

const commandTiles = [
  { command: '/ban', desc: 'Veto a un miembro.' },
  { command: '/unban', desc: 'Retira un veto.' },
  { command: '/kick', desc: 'Expulsa a un miembro.' },
  { command: '/mute', desc: 'Silencia a un miembro.' },
  { command: '/unmute', desc: 'Devuelve la voz.' },
  { command: '/lock', desc: 'Cierra un canal.' },
  { command: '/unlock', desc: 'Abre un canal.' },
  { command: '/clear', desc: 'Borra mensajes.' },
  { command: '/addrole', desc: 'Añade un rol.' },
  { command: '/removerole', desc: 'Retira un rol.' },
];

function InviteAction({ dark = false }: { dark?: boolean }) {
  if (!DISCORD_INVITE_URL) {
    return (
      <span className={`setup-note${dark ? ' setup-note-dark' : ''}`} role="note">
        Enlace de invitación pendiente de configurar por el equipo.
      </span>
    );
  }
  return (
    <a
      className={`button${dark ? ' button-dark' : ''}`}
      href={DISCORD_INVITE_URL}
      target="_blank"
      rel="noopener noreferrer"
      data-testid="link-add-vortex"
    >
      Añadir a Discord <ArrowUpRight aria-hidden="true" />
    </a>
  );
}

function App() {
  const [menuOpen, setMenuOpen] = useState(false);
  const closeMenu = () => setMenuOpen(false);

  return (
    <div className="site">
      <a className="skip-link" href="#contenido">Saltar al contenido</a>
      <header className="topbar">
        <div className="wrap nav-inner">
          <a className="brand" href="#inicio" aria-label="Vortex Casino Bot, inicio" onClick={closeMenu}>
            <span className="brand-mark" aria-hidden="true"><span>V</span></span>
            <span>VORTEX <span style={{ color: 'var(--gold)' }}>CASINO</span></span>
          </a>
          <nav id="mobile-navigation" className={`nav-links${menuOpen ? ' open' : ''}`} aria-label="Navegación principal">
            <a href="#rangos" onClick={closeMenu}>Rangos</a>
            <a href="#experiencia" onClick={closeMenu}>La experiencia</a>
            <a href="#moderacion" onClick={closeMenu}>Moderación</a>
          </nav>
          <InviteAction />
          <button
            type="button"
            className="menu-toggle"
            onClick={() => setMenuOpen((open) => !open)}
            aria-label={menuOpen ? 'Cerrar menú' : 'Abrir menú'}
            aria-expanded={menuOpen}
            aria-controls="mobile-navigation"
            data-testid="button-toggle-menu"
          >
            {menuOpen ? <X size={19} /> : <Menu size={19} />}
          </button>
        </div>
      </header>

      <main id="contenido">
        <section className="hero" id="inicio" aria-labelledby="hero-title">
          <div className="wrap hero-grid">
            <div className="hero-copy">
              <div className="hero-kicker eyebrow fade-up">La mesa está abierta</div>
              <h1 className="display fade-up delay-1" id="hero-title">
                Tu server.
                <span>Tu casino.</span>
              </h1>
              <p className="hero-lede fade-up delay-2">
                Vortex convierte tu comunidad de Discord en un club de casino:
                reúne monedas, sube de rango y juega por llegar hasta Obsidiana.
              </p>
              <div className="hero-actions fade-up delay-2">
                <InviteAction />
                <a className="text-link" href="#rangos" data-testid="link-explore-ranks">
                  Descubre los rangos <ArrowDownRight size={15} aria-hidden="true" />
                </a>
              </div>
              <div className="hero-note"><i aria-hidden="true" /> Para comunidades de Discord</div>
            </div>
            <div className="stage" aria-label="Emblema de Vortex Casino con fichas y rango VIP">
              <div className="orbit one" aria-hidden="true" />
              <div className="orbit two" aria-hidden="true" />
              <div className="coin" aria-hidden="true">
                <div className="coin-inner"><strong>V</strong><small>VORTEX · CASINO</small></div>
              </div>
              <div className="float-chip chip-rank"><small>Rango actual</small><b>VIP</b></div>
              <div className="float-chip chip-bet"><small>Tu próxima meta</small><b>Obsidiana</b></div>
              <div className="stage-label">Entra a la mesa. Gánate el nombre.</div>
            </div>
          </div>
        </section>

        <div className="ticker" aria-label="Un club de casino para tu comunidad">
          <div className="wrap ticker-track">
            <span className="ticker-item">Monedas para reunir</span>
            <span className="ticker-item">Rangos para conquistar</span>
            <span className="ticker-item">Un club en tu Discord</span>
            <span className="ticker-item">Moderación con slash commands</span>
          </div>
        </div>

        <section className="section rank-section" id="rangos" aria-labelledby="rank-title">
          <div className="wrap">
            <div className="section-head">
              <div>
                <div className="eyebrow">De la primera ficha a la leyenda</div>
                <h2 className="display" id="rank-title">Once rangos.<br />Una cima.</h2>
              </div>
              <p>Empieza en VIP. Reúne monedas y avanza por una escalera de rangos que termina donde pocos llegan: Obsidiana.</p>
            </div>
            <div className="rank-grid">
              {ranks.map((rank, index) => (
                <article className="rank" key={rank} data-testid={`rank-${rank.toLowerCase()}`}>
                  <span className="rank-num">RANGO {String(index + 1).padStart(2, '0')}</span>
                  <i className="rank-stone" aria-hidden="true" />
                  <b>{rank}</b>
                  <small>{index === 0 ? 'La entrada' : index === ranks.length - 1 ? 'La cima' : 'Siguiente nivel'}</small>
                </article>
              ))}
            </div>
            <div className="rank-footer">Tu nombre cambia. Tu historia también.</div>
          </div>
        </section>

        <section className="section experience" id="experiencia" aria-labelledby="experience-title">
          <div className="wrap experience-grid">
            <div className="experience-intro">
              <div className="eyebrow">No es solo otra sala</div>
              <h2 className="display" id="experience-title">La mesa<br />es vuestra.</h2>
              <p>Vortex pone la emoción del casino en el centro de la comunidad. Cada moneda cuenta para acercarte un poco más al siguiente rango.</p>
              <a className="text-link" href="#rangos" data-testid="link-see-ladder">
                Ver la escalera completa <ArrowDownRight size={15} aria-hidden="true" />
              </a>
            </div>
            <div className="feature-list">
              <article className="feature">
                <span className="feature-index">01</span>
                <div>
                  <h3>Una economía que se siente</h3>
                  <p>Las monedas son el pulso del club. Reúnelas y dales sentido mientras compartes la mesa con tu comunidad.</p>
                  <span className="feature-tag">Monedas de comunidad</span>
                </div>
              </article>
              <article className="feature">
                <span className="feature-index">02</span>
                <div>
                  <h3>El rango se gana</h3>
                  <p>De VIP a Obsidiana, cada escalón marca el camino. La cima tiene nombre; ahora toca hacerte con él.</p>
                  <span className="feature-tag">11 rangos · 1 destino</span>
                </div>
              </article>
              <article className="feature">
                <span className="feature-index">03</span>
                <div>
                  <h3>La casa sigue en orden</h3>
                  <p>Quienes administran el servidor cuentan con comandos slash para moderar miembros, canales, mensajes y roles.</p>
                  <span className="feature-tag">Herramientas para admins</span>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section className="section moderation" id="moderacion" aria-labelledby="mod-title">
          <div className="wrap mod-layout">
            <div className="mod-copy">
              <div className="eyebrow">Fuera de la mesa, control total</div>
              <h2 className="display" id="mod-title">Administra<br />sin salir del chat.</h2>
              <p>Herramientas de moderación con comandos slash para que el equipo del servidor mantenga cada canal en su sitio.</p>
              <div className="mod-foot"><ShieldCheck aria-hidden="true" /> Acciones claras para el equipo de moderación</div>
            </div>
            <div className="command-window" aria-label="Vista de comandos de moderación disponibles">
              <div className="window-bar">
                <span className="window-dots" aria-hidden="true"><i /><i /><i /></span>
                <span>COMANDOS DE MODERACIÓN</span>
                <span>VORTEX</span>
              </div>
              <div className="command-list">
                {moderationCommands.map(({ command, action }) => (
                  <div className="command-row" key={command}>
                    <span className="slash" aria-hidden="true">/</span>
                    <span className="command-name">{command.replaceAll('/', '')}</span>
                    <span className="command-group">{action}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="section commands-section" aria-labelledby="commands-title">
          <div className="wrap">
            <div className="section-head">
              <div>
                <div className="eyebrow">Herramientas de administración</div>
                <h2 className="display" id="commands-title">Cada acción.<br />Un comando.</h2>
              </div>
              <p>Acciones directas para miembros, canales y roles. Los comandos de Vortex se usan desde la interfaz slash de Discord.</p>
            </div>
            <div className="commands-grid">
              {commandTiles.map(({ command, desc }) => (
                <article className="command-card" key={command} data-testid={`command-${command.slice(1)}`}>
                  <span>{command}</span>
                  <b>{command.slice(1)}</b>
                  <p>{desc}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="finale" aria-labelledby="finale-title">
          <div className="wrap">
            <div className="eyebrow">La mesa espera a tu comunidad</div>
            <h2 className="display" id="finale-title">¿Quién llega<br />a Obsidiana?</h2>
            <p>Abre el club en tu servidor y deja que empiece la carrera por los rangos.</p>
            <InviteAction dark />
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="wrap footer-inner">
          <div className="footer-brand">VORTEX CASINO BOT</div>
          <span>Un club de casino hecho para Discord.</span>
          <div className="footer-links">
            <a href="#rangos">Rangos</a>
            <a href="#experiencia">Experiencia</a>
            <a href="#moderacion">Moderación</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

export default App;
