import firebase from "firebase/compat/app";
import "firebase/compat/auth";

let isInitialized = false;

export const initFirebase = async () => {
  if (isInitialized) return firebase;
  try {
    const response = await fetch("/api/config?t=" + Date.now());
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
