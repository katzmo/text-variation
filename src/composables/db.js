import { openDB } from 'idb'
import { onMounted, ref } from 'vue'

const dbName = 'TextTool'
const storeNames = ['documents', 'segments']
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
            store.createIndex('id', 'id', { unique: true })

            if (storeName !== 'documents') {
              store.createIndex('docKey', 'docKey') // index releated document
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
      // Update data after changes
      if (['put', 'add', 'delete', 'clear'].includes(action)) {
        stores[storeName].value = await dbExec(storeName, 'getAll')
      }
      return resolved
    } catch (err) {
      console.warn(err)
    }
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
