package main

import (
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/MicahParks/keyfunc/v3"
	"github.com/golang-jwt/jwt/v5"
)

var (
	requireAuth     bool
	cognitoIssuer   string
	cognitoClientID string
	jwks            keyfunc.Keyfunc
)

// initAuth sets up the JWKS-based verifier. Only called when REQUIRE_AUTH is
// true - local/dev deployments with no Cognito user pool never hit this.
func initAuth(userPoolID, clientID, region string) error {
	cognitoIssuer = "https://cognito-idp." + region + ".amazonaws.com/" + userPoolID
	cognitoClientID = clientID

	k, err := keyfunc.NewDefault([]string{cognitoIssuer + "/.well-known/jwks.json"})
	if err != nil {
		return fmt.Errorf("fetching JWKS: %w", err)
	}
	jwks = k
	return nil
}

// verifyIDToken re-verifies the id_token cookie ourselves rather than trusting
// that CloudFront's Lambda@Edge already checked it - defense in depth, and it
// means a request that reaches ai-gateway directly (bypassing CloudFront)
// still can't get through without a valid session.
func verifyIDToken(r *http.Request) (userID string, err error) {
	cookie, err := r.Cookie("id_token")
	if err != nil {
		return "", errors.New("missing id_token cookie")
	}

	token, err := jwt.Parse(cookie.Value, jwks.Keyfunc, jwt.WithValidMethods([]string{"RS256"}))
	if err != nil || !token.Valid {
		return "", fmt.Errorf("invalid id token: %w", err)
	}

	claims, ok := token.Claims.(jwt.MapClaims)
	if !ok {
		return "", errors.New("unexpected claims type")
	}

	iss, _ := claims.GetIssuer()
	if iss != cognitoIssuer {
		return "", errors.New("unexpected issuer")
	}
	if tokenUse, _ := claims["token_use"].(string); tokenUse != "id" {
		return "", errors.New("not an id token")
	}
	aud, _ := claims["aud"].(string)
	if aud != cognitoClientID {
		return "", errors.New("unexpected audience")
	}
	exp, err := claims.GetExpirationTime()
	if err != nil || exp == nil || exp.Before(time.Now()) {
		return "", errors.New("token expired")
	}

	sub, _ := claims["sub"].(string)
	if sub == "" {
		return "", errors.New("missing sub claim")
	}
	return sub, nil
}
