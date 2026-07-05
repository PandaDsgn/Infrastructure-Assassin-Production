import firebase from "firebase/compat/app";
import "firebase/compat/auth";

let isInitialized = false;

const API_BASE_URL = import.meta.env.VITE_API_URL || "";

export const initFirebase = async () => {
  if (isInitialized) return firebase;
  try {
    const response = await fetch(`${API_BASE_URL}/api/config?t=${Date.now()}`);
    if (!response.ok) {
      throw new Error(`Config fetch failed: ${response.status}`);
    }
    const firebaseConfig = await response.json();
    firebase.initializeApp(firebaseConfig);
    isInitialized = true;
    return firebase;
  } catch (error) {
    console.error("Failed to load Firebase config from server.", error);
    throw error;
  }
};

export const getAuth = () => firebase.auth();
