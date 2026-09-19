import React, {useEffect} from 'react';
import {StatusBar, Platform} from 'react-native';
import FlashMessage from 'react-native-flash-message';
import RootNavigator from './src/navigation/RootNavigator';
import {useStore} from './src/store';

// Firebase messaging setup
let messaging: any = null;
try {
  messaging = require('@react-native-firebase/messaging').default;
} catch {}

export default function App() {
  const {loadStrategies, loadSignals, loadScanners, addSignal} = useStore();

  useEffect(() => {
    // Load initial data
    loadStrategies();
    loadSignals();
    loadScanners();

    // Setup FCM
    if (messaging) {
      setupFCM();
    }
  }, []);

  const setupFCM = async () => {
    try {
      const authStatus = await messaging().requestPermission();
      const enabled =
        authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
        authStatus === messaging.AuthorizationStatus.PROVISIONAL;

      if (enabled) {
        const token = await messaging().getToken();
        // TODO: Register token with active scanners
        console.log('FCM Token:', token);
      }

      // Handle foreground notifications
      messaging().onMessage(async (remoteMessage: any) => {
        console.log('Foreground FCM:', remoteMessage);
        if (remoteMessage.data?.type === 'signal') {
          // Refresh signals
          loadSignals();
        }
      });

      // Handle background/quit tap
      messaging().onNotificationOpenedApp(async (remoteMessage: any) => {
        console.log('Notification opened app:', remoteMessage);
      });
    } catch (e) {
      console.warn('FCM setup failed:', e);
    }
  };

  return (
    <>
      <StatusBar
        barStyle="light-content"
        backgroundColor="#0D1117"
      />
      <RootNavigator />
      <FlashMessage position="top" />
    </>
  );
}
