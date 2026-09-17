import React, { useState, useEffect, useCallback } from 'react';
import { Session } from '@supabase/supabase-js';
import { supabase } from '../lib/supabase';
import { UserProfile } from '../types';

/**
 * Maps a Supabase Session to the application UserProfile shape.
 */
export function mapSessionToUserProfile(session: Session | null): UserProfile | null {
  if (!session?.user) return null;
  const u = session.user;
  const metadata = u.user_metadata || {};
  return {
    id: u.id,
    name: metadata.full_name || metadata.name || u.email?.split('@')[0] || 'User',
    email: u.email || '',
    avatarUrl: metadata.avatar_url || metadata.picture,
    accessToken: session.access_token,
  };
}

export interface AuthSessionHook {
  user: UserProfile | null;
  accessToken: string | null;
  loading: boolean;
  error: string | null;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
  invalidateSession: () => Promise<void>;
  setUser: React.Dispatch<React.SetStateAction<UserProfile | null>>;
}

/**
 * Encapsulates Supabase authentication lifecycle, session restoration,
 * and auth listener subscriptions.
 */
export function useAuthSession(): AuthSessionHook {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    // 1. Initial Session Restoration
    supabase.auth
      .getSession()
      .then(({ data: { session }, error: sessionError }) => {
        if (!isMounted) return;
        if (sessionError) {
          setError(sessionError.message);
          setUser(null);
        } else if (session) {
          setUser(mapSessionToUserProfile(session));
        } else {
          setUser(null);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err?.message || 'Failed to restore authentication session');
        setUser(null);
      })
      .finally(() => {
        if (isMounted) {
          setLoading(false);
        }
      });

    // 2. Listen for auth state changes (e.g. OAuth redirect, token refresh, sign-out)
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!isMounted) return;
      if (session) {
        setUser(mapSessionToUserProfile(session));
      } else {
        setUser(null);
      }
      setLoading(false);
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, []);

  const signInWithGoogle = useCallback(async () => {
    setError(null);
    const { error: signInError } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: window.location.origin,
      },
    });
    if (signInError) {
      setError(signInError.message);
      throw signInError;
    }
  }, []);

  const signOut = useCallback(async () => {
    setError(null);
    try {
      const { error: signOutError } = await supabase.auth.signOut();
      if (signOutError) {
        setError(signOutError.message);
        throw signOutError;
      }
    } finally {
      setUser(null);
    }
  }, []);

  const invalidateSession = useCallback(async () => {
    setError('Authentication session expired or invalid. Returned to guest mode.');
    try {
      await supabase.auth.signOut();
    } catch {
      // Best-effort cleanup on invalidation
    } finally {
      setUser(null);
    }
  }, []);

  return {
    user,
    accessToken: user?.accessToken || null,
    loading,
    error,
    signInWithGoogle,
    signOut,
    invalidateSession,
    setUser,
  };
}
