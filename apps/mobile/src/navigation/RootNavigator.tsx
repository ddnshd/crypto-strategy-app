import React from 'react';
import {NavigationContainer} from '@react-navigation/native';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {createStackNavigator} from '@react-navigation/stack';

// Screens
import HomeScreen from '../screens/HomeScreen';
import StrategyBuilderScreen from '../screens/StrategyBuilderScreen';
import StrategyLibraryScreen from '../screens/StrategyLibraryScreen';
import SignalFeedScreen from '../screens/SignalFeedScreen';
import BacktestScreen from '../screens/BacktestScreen';
import StrategyDetailScreen from '../screens/StrategyDetailScreen';

const Tab = createBottomTabNavigator();
const Stack = createStackNavigator();

function StrategyStack() {
  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: {backgroundColor: '#0D1117'},
        headerTintColor: '#E6EDF3',
        headerTitleStyle: {fontWeight: '700'},
      }}>
      <Stack.Screen
        name="StrategyLibrary"
        component={StrategyLibraryScreen}
        options={{title: 'Library Strategi'}}
      />
      <Stack.Screen
        name="StrategyDetail"
        component={StrategyDetailScreen}
        options={{title: 'Detail Strategi'}}
      />
      <Stack.Screen
        name="Backtest"
        component={BacktestScreen}
        options={{title: 'Backtest'}}
      />
    </Stack.Navigator>
  );
}

export type RootTabParamList = {
  Home: undefined;
  Builder: undefined;
  Library: undefined;
  Signals: undefined;
};

export type StrategyStackParamList = {
  StrategyLibrary: undefined;
  StrategyDetail: {strategyId: string};
  Backtest: {strategyId: string};
};

export default function RootNavigator() {
  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={{
          tabBarStyle: {
            backgroundColor: '#0D1117',
            borderTopColor: '#30363D',
          },
          tabBarActiveTintColor: '#58A6FF',
          tabBarInactiveTintColor: '#8B949E',
          headerStyle: {backgroundColor: '#0D1117'},
          headerTintColor: '#E6EDF3',
          headerTitleStyle: {fontWeight: '700'},
        }}>
        <Tab.Screen
          name="Home"
          component={HomeScreen}
          options={{
            title: 'Dashboard',
            tabBarLabel: 'Dashboard',
          }}
        />
        <Tab.Screen
          name="Builder"
          component={StrategyBuilderScreen}
          options={{
            title: 'AI Builder',
            tabBarLabel: 'Builder',
          }}
        />
        <Tab.Screen
          name="Library"
          component={StrategyStack}
          options={{
            title: 'Library',
            tabBarLabel: 'Library',
            headerShown: false,
          }}
        />
        <Tab.Screen
          name="Signals"
          component={SignalFeedScreen}
          options={{
            title: 'Sinyal',
            tabBarLabel: 'Sinyal',
          }}
        />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
