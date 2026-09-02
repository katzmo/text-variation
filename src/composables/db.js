import { openDB } from 'idb'
import { onMounted, ref } from 'vue'

const dbName = 'TextTool'
const storeNames = ['documents', 'groups', 'scores', 'segments', 'tokens']
const stores = Object.fromEntries(storeNames.map((key) => [key, ref([])]))
let db = null

/**
 * A composable for accessing IndexedDB stores.
 *
 * @param {string} storeName - The name of the store.
 * @returns {Object} An object containing db-related functions and reactive properties.
 */
export const useIndexedDBStore = () => {
  /**
   * Initializes (or opens) the IndexedDB database and ensures the object store exists.
   *
   * @returns {IDBPDatabase<any>}
   */
  const initDB = async () => {
    if (db) return db
    return await openDB(dbName, 1, {
      /**
       * Runs when the database is created or upgraded.
       *
       * @param {import('idb').IDBPDatabase<any>} db
       */
      upgrade(db) {
        for (const storeName of storeNames) {
          if (!db.objectStoreNames.contains(storeName)) {
            const store = db.createObjectStore(storeName, { keyPath: 'key', autoIncrement: true })
            if (['documents', 'groups', 'segments'].includes(storeName)) {
              store.createIndex('id', 'id', { unique: true })
            }
            if (['segments', 'tokens'].includes(storeName)) {
              store.createIndex('docKey', 'docKey') // index releated document
            }
            if ('tokens' === storeName) {
              store.createIndex('idByDoc', ['id', 'docKey'], { unique: true }) // index tokens by document
            }
            if ('scores' === storeName) {
              store.createIndex('docKeys', 'docKeys') // combined value
              store.createIndex('docKey', 'docKeys', { multiEntry: true }) // single values
              store.createIndex('segKeys', 'segKeys', { unique: true }) // combined value
              store.createIndex('segKey', 'segKeys', { multiEntry: true }) // single values
            }
            if ('groups' === storeName) {
              store.createIndex('segKey', 'segKeys', { multiEntry: true }) // single values
            }
          }
        }
      },
    })
  }

  /**
   * Execute a idb shortcut function on the initialized DB.
   *
   * @param {string} action - The wrapped function's name.
   * @param  {...any} args - Arguments to pass on.
   * @returns {*} The wrapped functions return value.
   */
  const dbExec = async (storeName, action, ...args) => {
    try {
      db = await initDB()
      const resolved = await db[action](storeName, ...args)
      // Cascade deletions
      if (action === 'delete' && storeName === 'documents') {
        cascadeDelete('docKey', args[0])
      }
      // Cascade clear
      else if (action === 'clear' && storeName === 'documents') {
        await Promise.all(
          storeNames.filter((name) => name !== 'documents').map((name) => dbExec(name, action)),
        )
      }
      // Update data after changes
      if (['put', 'add', 'delete', 'clear'].includes(action)) {
        stores[storeName].value = await dbExec(storeName, 'getAll')
      }
      return resolved
    } catch (err) {
      console.warn(err)
    }
  }

  /**
   * Delete objects from all stores with a certain index.
   *
   * @param {string} indexName - The index to query.
   * @param {*} value - The value to delete.
   */
  const cascadeDelete = async (indexName, value) => {
    storeNames.forEach(async (storeName) => {
      let keys = []
      try {
        keys = await db.getAllKeysFromIndex(storeName, indexName, value)
      } catch (err) {
        if (err.name === 'NotFoundError') return
        throw err
      }
      await Promise.all(keys.map((key) => db.delete(storeName, key)))
      // Upadate reference
      stores[storeName].value = await dbExec(storeName, 'getAll')
    })
  }

  onMounted(async () => {
    // Initialize data
    storeNames.forEach(
      async (storeName) => (stores[storeName].value = await dbExec(storeName, 'getAll')),
    )
  })

  return {
    ...stores,
    db,
    dbExec,
  }
}
