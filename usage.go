package main

import (
	"context"
	"strconv"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb"
	"github.com/aws/aws-sdk-go-v2/service/dynamodb/types"
)

var (
	usageTable      string
	dailyTokenLimit int
	dynamoClient    *dynamodb.Client
)

func today() string {
	return time.Now().UTC().Format("2006-01-02")
}

// checkUnderLimit reports whether userID still has quota left today. A
// missing row (first request of the day) always passes.
func checkUnderLimit(ctx context.Context, userID string) (bool, error) {
	out, err := dynamoClient.GetItem(ctx, &dynamodb.GetItemInput{
		TableName: aws.String(usageTable),
		Key: map[string]types.AttributeValue{
			"user_id": &types.AttributeValueMemberS{Value: userID},
			"date":    &types.AttributeValueMemberS{Value: today()},
		},
	})
	if err != nil {
		return false, err
	}
	if out.Item == nil {
		return true, nil
	}

	used, ok := out.Item["tokens_used"].(*types.AttributeValueMemberN)
	if !ok {
		return true, nil
	}
	n, err := strconv.Atoi(used.Value)
	if err != nil {
		return true, nil
	}
	return n < dailyTokenLimit, nil
}

// recordUsage atomically adds tokens to today's counter for userID, creating
// the row (with a TTL a few days out) on first use of the day.
func recordUsage(ctx context.Context, userID string, tokens int) error {
	expiresAt := time.Now().UTC().Truncate(24 * time.Hour).Add(72 * time.Hour).Unix()

	_, err := dynamoClient.UpdateItem(ctx, &dynamodb.UpdateItemInput{
		TableName: aws.String(usageTable),
		Key: map[string]types.AttributeValue{
			"user_id": &types.AttributeValueMemberS{Value: userID},
			"date":    &types.AttributeValueMemberS{Value: today()},
		},
		UpdateExpression: aws.String("ADD tokens_used :n SET expires_at = if_not_exists(expires_at, :ttl)"),
		ExpressionAttributeValues: map[string]types.AttributeValue{
			":n":   &types.AttributeValueMemberN{Value: strconv.Itoa(tokens)},
			":ttl": &types.AttributeValueMemberN{Value: strconv.FormatInt(expiresAt, 10)},
		},
	})
	return err
}
