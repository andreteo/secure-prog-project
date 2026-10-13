// Browser verification for password login, session restore, and logout.
// Run against an initialized local secure server with DEMO_PASSWORD set.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');

(async () => {
  const base = process.env.BASE_URL || 'http://127.0.0.1:5001';
  const password = process.env.DEMO_PASSWORD;
  if (!password) throw new Error('Set DEMO_PASSWORD for the Doon test account.');
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base);
    await page.getByLabel('Username', { exact: true }).fill('doon');
    await page.getByLabel('Password', { exact: true }).fill('wrong-password');
    await page.getByRole('button', { name: 'Open library' }).click();
    await page.getByRole('alert').getByText('Username or password does not exist.').waitFor();
    assert.equal(await page.getByRole('heading', { name: 'Doon’s library' }).count(), 0);

    await page.getByLabel('Password', { exact: true }).fill(password);
    await page.getByRole('button', { name: 'Open library' }).click();
    await page.getByRole('heading', { name: 'Doon’s library' }).waitFor();
    await page.getByRole('heading', { name: 'The Hobbit', exact: true }).waitFor();
    assert.equal(await page.locator('.book').count(), 3);
    console.log('PASS password login opens Doon’s library');

    await page.reload();
    await page.getByRole('heading', { name: 'Doon’s library' }).waitFor();
    assert.equal(await page.getByLabel('Password', { exact: true }).count(), 0);
    console.log('PASS session restores after reload without localStorage identity');

    await page.getByRole('button', { name: '+ Add book', exact: true }).click();
    await page.getByLabel('Title', { exact: true }).fill('Authentication browser check');
    await page.getByLabel('Author', { exact: true }).fill('Test');
    await page.getByRole('button', { name: 'Save book', exact: true }).click();
    await page.getByRole('heading', { name: 'Authentication browser check', exact: true }).waitFor();
    const book = page.locator('article.book').filter({ has: page.getByRole('heading', { name: 'Authentication browser check', exact: true }) });
    await book.getByRole('button', { name: 'Remove', exact: true }).click();
    await book.getByRole('button', { name: 'Yes, remove', exact: true }).click();
    await page.getByRole('heading', { name: 'Authentication browser check', exact: true }).waitFor({ state: 'detached' });
    console.log('PASS authenticated book write uses request token');

    await page.getByRole('button', { name: 'Sign out', exact: true }).click();
    await page.getByLabel('Password', { exact: true }).waitFor();
    await page.goto(base + '/users/1/dashboard');
    await page.getByLabel('Password', { exact: true }).waitFor();
    assert.equal((await context.request.get(base + '/api/session')).status(), 401);
    assert.deepEqual(errors, []);
    console.log('PASS logout invalidates session and protected page requires login');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
