import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {Platform} from 'react-native';

// Backend URL — ganti PROD_URL dengan URL Railway saat deploy production.
// APK debug di HP yang sama dengan backend Termux: pakai 127.0.0.1:8001.
const DEV_URL =
  Platform.OS === 'android'
    ? 'http://10.0.2.2:8001' // Android emulator -> host machine
    : 'http://localhost:8001'; // iOS simulator
const PROD_URL = 'http://127.0.0.1:8001'; // backend Termux di HP yang sama
const BASE_URL = __DEV__ ? DEV_URL : PROD_URL;

const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Device ID management
let _deviceId: string | null = null;

export async function getDeviceId(): Promise<string> {
  if (_deviceId) return _deviceId;

  const stored = await AsyncStorage.getItem('device_id');
  if (stored) {
    _deviceId = stored;
    return stored;
  }

  // Generate new device ID
  const newId = `device_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  await AsyncStorage.setItem('device_id', newId);
  _deviceId = newId;
  return newId;
}

// Request interceptor — add device_id header
apiClient.interceptors.request.use(async config => {
  const deviceId = await getDeviceId();
  config.headers['X-Device-Id'] = deviceId;
  return config;
});

// Response interceptor — global error handling
apiClient.interceptors.response.use(
  response => response,
  error => {
    const message =
      error.response?.data?.detail ||
      error.message ||
      'Terjadi kesalahan jaringan';
    console.error('API Error:', message, error.config?.url);
    return Promise.reject(new Error(message));
  },
);

export {apiClient, BASE_URL};
