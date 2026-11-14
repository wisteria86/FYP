import test from 'node:test'
import assert from 'node:assert/strict'
import { portraitTraits, hash, HAIR_STYLE, SKIN } from './call/portraitTraits.mjs'

test('the same character always gets the same look', () => {
  assert.deepEqual(portraitTraits('Alex', 'Supplier representative'), portraitTraits('Alex', 'Supplier representative'))
  assert.deepEqual(portraitTraits(' alex ', 'SUPPLIER REPRESENTATIVE'), portraitTraits('Alex', 'Supplier representative'))
})

test('different characters get varied looks from the allowed palettes', () => {
  const names = ['Alex', 'Maya', 'Omar', 'Sara', 'Lena', 'Bilal', 'Priya', 'Tom', 'Ayesha', 'Chen', 'Fatima', 'Jonas']
  const looks = names.map(name => portraitTraits(name, 'Colleague'))
  assert.ok(new Set(looks.map(look => look.hairStyle)).size >= 4)
  assert.ok(new Set(looks.map(look => look.skin)).size >= 3)
  for (const look of looks) {
    assert.ok(HAIR_STYLE.includes(look.hairStyle))
    assert.ok(SKIN.includes(look.skin))
    assert.ok(look.faceWidth >= 37 && look.faceWidth <= 41)
  }
})

test('the hash is stable', () => {
  assert.equal(hash('Hikari'), hash('Hikari'))
  assert.notEqual(hash('Hikari'), hash('hikari'))
})
