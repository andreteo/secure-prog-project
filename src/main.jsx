import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const EMPTY_BOOK = { title: '', author: '', status: 'To read', notes: '' };
const STATUSES = ['To read', 'Reading', 'Finished'];

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...options.headers },
  });
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
  return data;
}

function readIdentity() {
  try { return JSON.parse(localStorage.getItem('baseline-user')) || null; }
  catch { return null; }
}

function App() {
  // Display convenience only: this local state is NOT an authenticated session.
  const [identity, setIdentity] = useState(readIdentity);
  const [path, setPath] = useState(window.location.pathname);
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);
  function navigate(next) {
    window.history.pushState({}, '', next);
    setPath(next);
    window.scrollTo(0, 0);
  }
  function login(user) {
    localStorage.setItem('baseline-user', JSON.stringify(user));
    setIdentity(user);
    navigate(`/users/${user.id}/dashboard`);
  }
  function logout() {
    localStorage.removeItem('baseline-user');
    setIdentity(null);
    navigate('/');
  }
  const match = path.match(/^\/users\/(\d+)\/dashboard\/?$/);
  const isAdminPage = /^\/admin\/?$/.test(path);
  return <>
    <div className="baseline-strip">600IT - Secure Programming</div>
    <header className="site-header">
      <a className="brand" href="/" onClick={e => { e.preventDefault(); navigate('/'); }}>
        <span className="brand-icon" aria-hidden="true">▤</span> Book Ledger
      </a>
      <nav aria-label="Main navigation">
        {identity && <>
          <a href={`/users/${identity.id}/dashboard`} onClick={e => { e.preventDefault(); navigate(`/users/${identity.id}/dashboard`); }}>My library</a>
          <span className="identity">Signed in as <strong>{identity.display_name}</strong></span>
          <button className="text-button" onClick={logout}>Sign out</button>
        </>}
        {!identity && path !== '/' && <a href="/" onClick={e => { e.preventDefault(); navigate('/'); }}>Sign in</a>}
      </nav>
    </header>
    <main>
      {path === '/' ? <Login onLogin={login} /> :
        isAdminPage ? <Library key="admin" admin /> :
        match ? <Library key={match[1]} userId={Number(match[1])} /> :
        <section className="empty"><h1>Page not found</h1><p>That page is not part of your library.</p><a href="/">Return to sign in</a></section>}
    </main>
    <footer>Book Ledger <span>Sin Doon</span></footer>
  </>;
}

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError('');
    try { onLogin((await api('/api/login', { method: 'POST', body: JSON.stringify({ username }) })).user); }
    catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <section className="login-layout">
    <div className="intro">
      <p className="eyebrow">YOUR PERSONAL READING SPACE</p>
      <h1>A place for your<br />next chapter.</h1>
      <p>Keep track of your books, your reading progress, and the thoughts you want to remember.</p>
      <div className="intro-rule" />

    </div>
    <form className="login-form panel" onSubmit={submit}>
      <p className="eyebrow">WELCOME BACK</p>
      <h2>Open your library</h2>
      <br />
      <br />
      {/* <p className="muted">Enter a demo username to get started.</p> */}
      <label htmlFor="username">Username</label>
      <input id="username" name="username" autoComplete="username" placeholder="e.g. doon" value={username} onChange={e => setUsername(e.target.value)} required />
      {error && <p className="error" role="alert">{error}</p>}
      <button className="primary wide" disabled={busy}>{busy ? 'Opening…' : 'Open library →'}</button>
      <p className="demo-hint">Demo users: <code>doon</code>, <code>otherdoon</code>, <code>admin</code></p>
    </form>
  </section>;
}

function Library({ userId, admin = false }) {
  const [user, setUser] = useState(null);
  const [books, setBooks] = useState([]);
  const [query, setQuery] = useState('');
  const [appliedQuery, setAppliedQuery] = useState('');
  const [revision, setRevision] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [editor, setEditor] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    async function load() {
      try {
        const options = { signal: controller.signal };
        // V04: /admin loads returned API records straight into state. No role gate.
        const [profile, result] = await Promise.all([
          admin ? Promise.resolve(null) : api(`/api/users/${userId}`, options),
          api(admin ? '/api/admin/books' : `/api/users/${userId}/books?q=${encodeURIComponent(appliedQuery)}`, options),
        ]);
        if (!controller.signal.aborted) {
          setUser(profile?.user || null);
          setBooks(result.books);
          if (Object.hasOwn(result, 'affected_rows')) setNotice(`${result.affected_rows} row${result.affected_rows === 1 ? '' : 's'} updated by the SQL statement.`);
        }
      } catch (err) {
        if (err.name !== 'AbortError') { setError(err.message); setBooks([]); }
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }
    load();
    return () => controller.abort();
  }, [userId, admin, appliedQuery, revision]);

  async function removeBook(book) {
    setError(''); setDeleteBusy(true);
    try {
      await api(`/api/books/${book.id}`, { method: 'DELETE' });
      setDeleting(null); setNotice(`“${book.title}” was removed.`); setRevision(n => n + 1);
    } catch (err) { setError(err.message); }
    finally { setDeleteBusy(false); }
  }
  return <section className="library">
    <div className="page-heading">
      <div>
        <p className="eyebrow">{admin ? 'ADMINISTRATION' : 'PERSONAL LIBRARY'}</p>
        <h1>{admin ? 'All readers, all books' : user ? `${user.display_name}’s library` : 'Your library'}</h1>
        <p className="muted">{admin ? 'An overview of every reader’s books and private notes.' : 'Your reading list and the notes along the way.'}</p>
      </div>
      {!admin && user && <button className="primary" onClick={() => { setEditor({ ...EMPTY_BOOK }); setNotice(''); }}>+ Add book</button>}
    </div>
    <div className="summary" aria-label="Library summary">
      <div><strong>{books.length}</strong><span>{appliedQuery ? 'Search results' : 'Books in view'}</span></div>
      <div><strong>{books.filter(b => b.status === 'Reading').length}</strong><span>Currently reading</span></div>
      <div><strong>{books.filter(b => b.status === 'Finished').length}</strong><span>Finished</span></div>
      {admin && <div><strong>{new Set(books.map(b => b.user_id)).size}</strong><span>Readers</span></div>}
    </div>
    {!admin && <form className="search" onSubmit={e => { e.preventDefault(); setAppliedQuery(query); setRevision(n => n + 1); setNotice(''); }}>
      <label htmlFor="search">Search your books</label>
      <div><input id="search" type="search" placeholder="Search by title" value={query} onChange={e => setQuery(e.target.value)} /><button className="secondary">Search</button>
        {appliedQuery && <button type="button" className="text-button" onClick={() => { setQuery(''); setAppliedQuery(''); }}>Clear</button>}</div>
    </form>}
    {notice && <p className="notice" role="status">{notice}</p>}
    {error && <p className="error" role="alert">{error}</p>}
    {editor && <BookEditor book={editor} userId={userId} onCancel={() => setEditor(null)} onSaved={book => {
      setEditor(null); setAppliedQuery(''); setQuery(''); setNotice(`“${book.title}” was saved.`); setRevision(n => n + 1);
    }} />}
    {loading ? <p role="status" className="empty">Loading your books…</p> :
      !error && books.length === 0 ? <div className="empty panel"><h2>{appliedQuery ? 'No matching books' : 'Your next chapter starts here'}</h2><p>{appliedQuery ? 'Try another title or clear the search.' : 'Add a book to begin your reading list.'}</p></div> :
      <div className="book-list">
        {books.map(book => <article className="book panel" key={book.id}>
          <div className="book-top">
            <div><p className="book-owner">{book.display_name || `User ${book.user_id}`} · Book #{book.id}</p><h2>{book.title || 'Untitled book'}</h2><p className="muted author">{book.author || 'Unknown author'}</p></div>
            <span className={`status status-${STATUSES.indexOf(book.status)}`}>{book.status}</span>
          </div>
          <div className="notes"><span className="notes-label">PRIVATE NOTES</span>
            {/* V05: intentionally renders untrusted stored HTML in this baseline. */}
            <div className="notes-content" dangerouslySetInnerHTML={{ __html: book.notes || '<span class="muted">No notes yet.</span>' }} />
          </div>
          {!admin && <div className="book-actions">
            {deleting === book.id ? <><span>Remove this book?</span><button disabled={deleteBusy} className="danger" onClick={() => removeBook(book)}>{deleteBusy ? 'Removing…' : 'Yes, remove'}</button><button disabled={deleteBusy} className="text-button" onClick={() => setDeleting(null)}>Cancel</button></> : <>
              <button className="text-button" onClick={() => { setEditor({ ...book }); setNotice(''); window.scrollTo({ top: 0, behavior: 'smooth' }); }}>Edit book</button>
              <button className="text-button muted" onClick={() => setDeleting(book.id)}>Remove</button>
            </>}
          </div>}
        </article>)}
      </div>}
  </section>;
}

function BookEditor({ book, userId, onCancel, onSaved }) {
  const [form, setForm] = useState(book);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setForm(book); setError(''); }, [book]);
  function change(e) { setForm(old => ({ ...old, [e.target.name]: e.target.value })); }
  async function save(e) {
    e.preventDefault(); setBusy(true); setError('');
    try {
      const result = await api(book.id ? `/api/books/${book.id}` : `/api/users/${userId}/books`, {
        method: book.id ? 'PUT' : 'POST', body: JSON.stringify(form),
      });
      onSaved(result.book);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }
  return <form className="editor panel" onSubmit={save} aria-label={book.id ? 'Edit book' : 'Add book'}>
    <h2>{book.id ? 'Edit book' : 'Add a book'}</h2>
    <div className="form-row"><div><label htmlFor="title">Title</label><input id="title" name="title" value={form.title} onChange={change} required autoFocus /></div>
      <div><label htmlFor="author">Author</label><input id="author" name="author" value={form.author} onChange={change} required /></div>
      <div><label htmlFor="status">Reading status</label><select id="status" name="status" value={form.status} onChange={change}>{STATUSES.map(status => <option key={status}>{status}</option>)}</select></div></div>
    <label htmlFor="notes">Private notes</label><textarea id="notes" name="notes" rows="3" value={form.notes} onChange={change} placeholder="What would you like to remember?" />
    {error && <p className="error" role="alert">{error}</p>}
    <div className="form-actions"><button className="primary" disabled={busy}>{busy ? 'Saving…' : 'Save book'}</button><button type="button" disabled={busy} className="secondary" onClick={onCancel}>Cancel</button></div>
  </form>;
}

createRoot(document.getElementById('root')).render(<App />);
