import axios from "axios";

import { runtimeConfig } from "./runtimeConfig";

export const networkClient = axios.create({
  baseURL: runtimeConfig.backendOrigin,
  timeout: 3000,
});

export function get(path, options = {}) {
  return networkClient.get(path, options);
}

export function post(path, data, options = {}) {
  return networkClient.post(path, data, options);
}
