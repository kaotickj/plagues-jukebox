package com.kaosium.kaostunes;

import java.net.URI;

final class StreamUrls {
    static final String GNB = "https://goodneighborblues.com/radio-stream";
    static boolean isValid(String value) {
        try {
            URI uri = new URI(value);
            String scheme = uri.getScheme();
            return ("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme))
                && uri.getHost() != null && uri.getUserInfo() == null && uri.getFragment() == null
                && (uri.getPort() == -1 || (uri.getPort() > 0 && uri.getPort() <= 65535));
        } catch (Exception e) { return false; }
    }
}
