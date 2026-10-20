import { LocalOutboxItem } from '../types'

const DB_NAME = 'shadowcomm_outbox_db'
const DB_VERSION = 1
const STORE_NAME = 'local_messages'
const OUTBOX_STORAGE_CEILING = 500
const OUTBOX_WARNING_THRESHOLD = 400

class OutboxDatabase {
  private dbPromise: Promise<IDBDatabase> | null = null

  async initPersistence(): Promise<boolean> {
    if (typeof navigator !== 'undefined' && navigator.storage && navigator.storage.persist) {
      try {
        return await navigator.storage.persist()
      } catch {
        return false
      }
    }
    return false
  }

  private getDB(): Promise<IDBDatabase> {
    if (this.dbPromise) return this.dbPromise

    this.dbPromise = new Promise((resolve, reject) => {
      if (typeof window === 'undefined' || !window.indexedDB) {
        reject(new Error('IndexedDB is not supported in this environment'))
        return
      }

      const request = indexedDB.open(DB_NAME, DB_VERSION)

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, {
            keyPath: 'client_idempotency_key',
          })
          store.createIndex('sync_status', 'sync_status', { unique: false })
          store.createIndex('created_at', 'created_at', { unique: false })
        }
      }

      request.onsuccess = () => {
        resolve(request.result)
      }

      request.onerror = () => {
        reject(request.error)
      }
    })

    return this.dbPromise
  }

  async countMessages(): Promise<number> {
    const db = await this.getDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly')
      const store = tx.objectStore(STORE_NAME)
      const req = store.count()
      req.onsuccess = () => resolve(req.result || 0)
      req.onerror = () => reject(req.error)
    })
  }

  async isNearCeiling(): Promise<boolean> {
    const count = await this.countMessages()
    return count >= OUTBOX_WARNING_THRESHOLD
  }

  async saveMessage(item: LocalOutboxItem): Promise<void> {
    const currentCount = await this.countMessages()
    if (currentCount >= OUTBOX_STORAGE_CEILING) {
      throw new Error(`Local offline outbox ceiling reached (${OUTBOX_STORAGE_CEILING} messages max). Please flush or clear outbox.`)
    }

    const db = await this.getDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      const req = store.put(item)
      req.onsuccess = () => resolve()
      req.onerror = () => reject(req.error)
    })
  }

  async getAllMessages(): Promise<LocalOutboxItem[]> {
    const db = await this.getDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly')
      const store = tx.objectStore(STORE_NAME)
      const req = store.getAll()
      req.onsuccess = () => resolve(req.result || [])
      req.onerror = () => reject(req.error)
    })
  }

  async updateSyncStatus(
    key: string,
    status: 'PENDING_LOCAL' | 'SYNCED' | 'FAILED_SYNC',
    errorMessage?: string
  ): Promise<void> {
    const db = await this.getDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      const getReq = store.get(key)
      getReq.onsuccess = () => {
        const item: LocalOutboxItem = getReq.result
        if (item) {
          item.sync_status = status
          if (errorMessage !== undefined) {
            item.error_message = errorMessage
          }
          const putReq = store.put(item)
          putReq.onsuccess = () => resolve()
          putReq.onerror = () => reject(putReq.error)
        } else {
          resolve()
        }
      }
      getReq.onerror = () => reject(getReq.error)
    })
  }

  async deleteMessage(key: string): Promise<void> {
    const db = await this.getDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      const req = store.delete(key)
      req.onsuccess = () => resolve()
      req.onerror = () => reject(req.error)
    })
  }

  async clear(): Promise<void> {
    const db = await this.getDB()
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite')
      const store = tx.objectStore(STORE_NAME)
      const req = store.clear()
      req.onsuccess = () => resolve()
      req.onerror = () => reject(req.error)
    })
  }
}

export const outboxDb = new OutboxDatabase()
