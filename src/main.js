import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

// import axios from 'axios'
// axios.defaults.withCredentials = true;
// axios.defaults.baseURL = 'http://127.0.0.1:8001'

createApp(App).use(ElementPlus).mount('#app')
