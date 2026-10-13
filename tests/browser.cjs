// Optional browser checks: requires Playwright and a local Chrome installation.
// Start the app first. Tests add/remove their own book; existing records are untouched.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const base = process.env.BASE_URL || 'http://127.0.0.1:5001';
  const errors = [];
  const results = [];
  let testId;
  page.on('pageerror', e => errors.push(e.message));
  const check = label => { results.push(label); console.log('PASS ' + label); };
  fs.mkdirSync('test-results', { recursive: true });
  try {
    await page.goto(base);
    await page.getByRole('heading', { name: 'Open your library' }).waitFor();
    await page.screenshot({ path: 'test-results/login.png', fullPage: true });
    await page.getByLabel('Username', { exact: true }).fill('doon');
    await page.getByRole('button', { name: 'Open library' }).click();
    await page.getByRole('heading', { name: 'Doon’s library' }).waitFor();
    await page.getByRole('heading', { name: 'The Hobbit', exact: true }).waitFor();
    assert.equal(await page.locator('.book').count(), 3);
    check('Username-only login opens Doon’s three-book library');
    await page.screenshot({ path: 'test-results/dashboard.png', fullPage: true });

    await page.getByRole('button', { name: '+ Add book', exact: true }).click();
    await page.getByLabel('Title', { exact: true }).fill('Browser verification book');
    await page.getByLabel('Author', { exact: true }).fill("O'Connor");
    await page.getByLabel('Private notes', { exact: true }).fill('Temporary test note.');
    await page.getByRole('button', { name: 'Save book', exact: true }).click();
    await page.getByRole('heading', { name: 'Browser verification book', exact: true }).waitFor();
    const records = await (await context.request.get(base + '/api/users/1/books')).json();
    testId = records.books.find(b => b.title === 'Browser verification book').id;
    await page.reload();
    await page.getByRole('heading', { name: 'Browser verification book', exact: true }).waitFor();
    let card = page.locator('article').filter({ has: page.getByRole('heading', { name: 'Browser verification book', exact: true }) });
    await card.getByRole('button', { name: 'Edit book', exact: true }).click();
    await page.getByLabel('Reading status', { exact: true }).selectOption('Finished');
    await page.getByLabel('Private notes', { exact: true }).fill('Updated through the browser.');
    await page.getByRole('button', { name: 'Save book', exact: true }).click();
    await card.getByText('Updated through the browser.', { exact: true }).waitFor();
    assert.equal(await card.locator('.status').textContent(), 'Finished');
    check('Create, reload persistence, and edit work through UI → API → SQLite');

    await page.getByLabel('Search your books').fill('Hobbit');
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await page.getByRole('button', { name: 'Clear', exact: true }).waitFor();
    await page.waitForFunction(() => document.querySelectorAll('.book').length === 1);
    assert.equal(await page.locator('.book h2').textContent(), 'The Hobbit');
    await page.getByRole('button', { name: 'Clear', exact: true }).click();
    await page.getByRole('heading', { name: 'Browser verification book', exact: true }).waitFor();
    card = page.locator('article').filter({ has: page.getByRole('heading', { name: 'Browser verification book', exact: true }) });
    await card.getByRole('button', { name: 'Remove', exact: true }).click();
    await card.getByRole('button', { name: 'Yes, remove', exact: true }).click();
    await page.waitForFunction(() => ![...document.querySelectorAll('.book h2')].some(e => e.textContent === 'Browser verification book'));
    assert.equal((await context.request.get(base + '/api/books/' + testId)).status(), 404);
    testId = undefined;
    check('Normal search and deletion work and persist');

    await page.goto(base + '/users/2/dashboard');
    await page.getByRole('heading', { name: 'Otherdoon’s library' }).waitFor();
    await page.getByRole('heading', { name: 'Dune', exact: true }).waitFor();
    assert.match(await page.locator('.identity').textContent(), /Doon/);
    check('URL change exposes Otherdoon’s dashboard while displayed identity remains Doon');

    await page.goto(base + '/admin');
    await page.getByRole('heading', { name: 'All readers, all books' }).waitFor();
    await page.getByRole('heading', { name: 'The Pragmatic Programmer', exact: true }).waitFor();
    assert.equal(await page.locator('.book').count(), 7);
    await page.screenshot({ path: 'test-results/admin.png', fullPage: true });
    check('Admin page displays all seven books and private notes to Doon');

    await page.goto(base + '/users/1/dashboard');
    await page.getByRole('heading', { name: 'The Hobbit', exact: true }).waitFor();
    await page.getByLabel('Search your books').fill('SELECT * FROM books');
    await page.getByRole('button', { name: 'Search', exact: true }).click();
    await page.getByRole('heading', { name: 'Dune', exact: true }).waitFor();
    assert.equal(await page.locator('.book').count(), 7);
    await page.screenshot({ path: 'test-results/direct-sql-query.png', fullPage: true });
    check('Direct SELECT statement exposes all users’ books');

    const originalOtherdoonNote = (await (await context.request.get(base + '/api/books/4')).json()).book.notes;
    try {
      await page.getByLabel('Search your books').fill("UPDATE books SET notes = 'Changed through SQL' WHERE id = 4");
      await page.getByRole('button', { name: 'Search', exact: true }).click();
      await page.getByText('1 row updated by the SQL statement.', { exact: true }).waitFor();
      const otherdoonBook = page.locator('article.book').filter({ has: page.getByRole('heading', { name: 'The Dispossessed', exact: true }) });
      await otherdoonBook.getByText('Changed through SQL', { exact: true }).waitFor();
      assert.equal((await (await context.request.get(base + '/api/books/4')).json()).book.notes, 'Changed through SQL');
      await page.screenshot({ path: 'test-results/direct-sql-update.png', fullPage: true });
      check('Direct UPDATE statement changes Otherdoon’s book through Doon’s dashboard');
    } finally {
      await context.request.put(base + '/api/books/4', { data: { notes: originalOtherdoonNote } });
    }

    const created = await (await context.request.post(base + '/api/users/1/books', { data: {
      title: 'Harmless HTML execution check', author: 'Test', status: 'To read',
      notes: '<img src="/missing-demo-image" onerror="document.body.dataset.xssDemo=\'executed\'">'
    } })).json();
    testId = created.book.id;
    await page.goto(base + '/users/1/dashboard');
    await page.waitForFunction(() => document.body.dataset.xssDemo === 'executed');
    await context.request.delete(base + '/api/books/' + testId);
    testId = undefined;
    check('Stored HTML can execute a harmless DOM marker (baseline XSS)');

    await page.getByRole('button', { name: 'Sign out', exact: true }).click();
    await page.goto(base + '/admin');
    await page.getByRole('heading', { name: 'The Pragmatic Programmer', exact: true }).waitFor();
    assert.equal(await page.locator('.book').count(), 7);
    check('Admin page remains accessible without pseudo-login');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(base);
    await page.getByRole('heading', { name: 'Open your library' }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
    await page.screenshot({ path: 'test-results/mobile-login.png', fullPage: true });
    check('Mobile login fits without horizontal overflow');
    assert.deepEqual(errors, []);
    check('No uncaught browser errors');
    fs.writeFileSync('test-results/browser-results.json', JSON.stringify({ results, errors }, null, 2));
  } finally {
    if (testId) await context.request.delete(base + '/api/books/' + testId);
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
