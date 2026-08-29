export interface Settings { pageSize: number; hideLowPriority: boolean; priorityThreshold: number; defaultHome: string }
const defaults: Settings={pageSize:20,hideLowPriority:false,priorityThreshold:70,defaultHome:'/'}
export function loadSettings():Settings{try{return{...defaults,...JSON.parse(localStorage.getItem('jlu-settings')??'{}')}}catch{return defaults}}
export function saveSettings(value:Settings){localStorage.setItem('jlu-settings',JSON.stringify(value))}
